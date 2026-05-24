from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request
from typing import Any


ENV_PROVIDER_KEY = "COURSE2KNOWLEDGE_LITE_DOSSIER_PROVIDER"
ENV_API_KEY = "COURSE2KNOWLEDGE_LITE_DOSSIER_API_KEY"
ENV_BASE_URL = "COURSE2KNOWLEDGE_LITE_DOSSIER_BASE_URL"
ENV_MODEL = "COURSE2KNOWLEDGE_LITE_DOSSIER_MODEL"
ENV_TIMEOUT_SECONDS = "COURSE2KNOWLEDGE_LITE_DOSSIER_TIMEOUT_SECONDS"
ENV_MAX_ATTEMPTS = "COURSE2KNOWLEDGE_LITE_DOSSIER_MAX_ATTEMPTS"
MOTHER_ENV_PROVIDER_KEY = "HUADU_LECTURE_DOSSIER_PROVIDER"
MOTHER_DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY"

_DOTENV_CACHE: dict[Path, dict[str, str]] = {}
_REQUEST_SEMAPHORES: dict[int, threading.BoundedSemaphore] = {}
_REQUEST_SEMAPHORE_LOCK = threading.Lock()


class LiteDossierProviderUnavailable(RuntimeError):
    pass


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    raw = str(line or "").strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        return None
    if raw.startswith("export "):
        raw = raw[len("export ") :].strip()
    key, value = raw.split("=", 1)
    key = key.strip().lstrip("\ufeff")
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_dotenv(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    cached = _DOTENV_CACHE.get(resolved)
    if cached is not None:
        return cached
    values: dict[str, str] = {}
    if resolved.exists():
        try:
            lines = resolved.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            lines = []
        for line in lines:
            parsed = _parse_dotenv_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if key and value:
                values[key] = value
    _DOTENV_CACHE[resolved] = values
    return values


def _repo_env_value(env_key: str) -> str:
    direct = str(os.getenv(env_key, "") or "").strip()
    if direct:
        return direct
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        values = _load_dotenv(env_path)
        value = str(values.get(env_key, "") or "").strip()
        if value:
            return value
    return ""


def _resolve_provider(explicit_provider: str | None) -> str:
    resolved = str(explicit_provider or _repo_env_value(ENV_PROVIDER_KEY) or "").strip()
    if resolved:
        return resolved
    mother_provider = _repo_env_value(MOTHER_ENV_PROVIDER_KEY)
    if mother_provider:
        return mother_provider
    if _repo_env_value(MOTHER_DEEPSEEK_API_KEY):
        return "deepseek"
    return ""


def _resolve_api_key(explicit_api_key: str | None, provider: str) -> str:
    resolved = str(explicit_api_key or _repo_env_value(ENV_API_KEY) or "").strip()
    if resolved:
        return resolved
    if provider == "deepseek":
        return _repo_env_value(MOTHER_DEEPSEEK_API_KEY)
    return ""


def _resolve_base_url(provider: str) -> str:
    configured = str(_repo_env_value(ENV_BASE_URL) or "").rstrip("/")
    if configured:
        return configured
    if provider == "deepseek":
        return "https://api.deepseek.com"
    return "https://api.openai.com/v1"


def _resolve_int_env(env_key: str, default: int, *, minimum: int = 1) -> int:
    raw_value = str(_repo_env_value(env_key) or "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, value)


def _get_request_semaphore(limit: int) -> threading.BoundedSemaphore:
    normalized_limit = max(1, int(limit or 1))
    with _REQUEST_SEMAPHORE_LOCK:
        semaphore = _REQUEST_SEMAPHORES.get(normalized_limit)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(normalized_limit)
            _REQUEST_SEMAPHORES[normalized_limit] = semaphore
    return semaphore


def request_compile_json(
    *,
    stage_name: str,
    system_prompt: str,
    user_prompt: str,
    provider: str | None = None,
    api_key: str | None = None,
    model: str = "",
    source_kind: str = "",
    multimodal_mode: str = "",
    max_tokens: int = 4096,
    max_concurrent_requests: int = 1,
    telemetry_recorder: Any = None,
    request_label: str = "",
    response_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    del source_kind, multimodal_mode, response_schema
    resolved_provider = _resolve_provider(provider)
    if not resolved_provider or resolved_provider == "off":
        raise LiteDossierProviderUnavailable(
            "No Lite dossier provider is configured. Set "
            "COURSE2KNOWLEDGE_LITE_DOSSIER_PROVIDER=openai_compatible, "
            "COURSE2KNOWLEDGE_LITE_DOSSIER_API_KEY, and optionally "
            "COURSE2KNOWLEDGE_LITE_DOSSIER_BASE_URL/MODEL. "
            "A parent Learning OS .env with DEEPSEEK_API_KEY is also accepted."
        )
    if resolved_provider not in {"openai_compatible", "deepseek"}:
        raise LiteDossierProviderUnavailable(f"Unsupported Lite dossier provider: {resolved_provider}")
    resolved_api_key = _resolve_api_key(api_key, resolved_provider)
    if not resolved_api_key:
        raise LiteDossierProviderUnavailable(
            "COURSE2KNOWLEDGE_LITE_DOSSIER_API_KEY is required, or DEEPSEEK_API_KEY for deepseek"
        )
    base_url = _resolve_base_url(resolved_provider)
    default_model = "deepseek-chat" if resolved_provider == "deepseek" else "gpt-4.1-mini"
    resolved_model = str(model or _repo_env_value(ENV_MODEL) or default_model).strip()
    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": int(max_tokens or 4096),
        "response_format": {"type": "json_object"},
    }
    if telemetry_recorder is not None and hasattr(telemetry_recorder, "record_attempt"):
        telemetry_recorder.record_attempt(stage=stage_name, label=request_label, provider=resolved_provider)
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout_seconds = _resolve_int_env(ENV_TIMEOUT_SECONDS, 240, minimum=30)
    max_attempts = _resolve_int_env(ENV_MAX_ATTEMPTS, 3, minimum=1)
    last_error: BaseException | None = None
    semaphore = _get_request_semaphore(max_concurrent_requests)
    with semaphore:
        for attempt_index in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    raw_response = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if telemetry_recorder is not None and hasattr(telemetry_recorder, "record_failure"):
                    telemetry_recorder.record_failure(
                        stage=stage_name,
                        label=request_label,
                        status=exc.code,
                        attempt=attempt_index,
                    )
                if exc.code < 500 or attempt_index >= max_attempts:
                    raise LiteDossierProviderUnavailable(f"Lite dossier provider HTTP {exc.code}: {body[:300]}") from exc
                last_error = exc
            except (OSError, TimeoutError) as exc:
                if telemetry_recorder is not None and hasattr(telemetry_recorder, "record_failure"):
                    telemetry_recorder.record_failure(
                        stage=stage_name,
                        label=request_label,
                        error=type(exc).__name__,
                        attempt=attempt_index,
                    )
                if attempt_index >= max_attempts:
                    raise LiteDossierProviderUnavailable(f"Lite dossier provider request failed: {exc}") from exc
                last_error = exc
            time.sleep(min(2 * attempt_index, 8))
        else:
            raise LiteDossierProviderUnavailable(f"Lite dossier provider request failed: {last_error}") from last_error
    content = str(
        (((raw_response.get("choices") or [{}])[0].get("message") or {}).get("content"))
        or ""
    ).strip()
    try:
        normalized = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LiteDossierProviderUnavailable("Lite dossier provider returned non-JSON content") from exc
    if not isinstance(normalized, dict):
        raise LiteDossierProviderUnavailable("Lite dossier provider JSON must be an object")
    if telemetry_recorder is not None and hasattr(telemetry_recorder, "record_success"):
        telemetry_recorder.record_success(stage=stage_name, label=request_label, provider=resolved_provider)
    return raw_response, normalized
