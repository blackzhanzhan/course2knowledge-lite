from __future__ import annotations

from typing import Any


DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS = 8192


class LectureDossierJsonParseFailure(RuntimeError):
    pass


def scrub_sensitive_text(value: Any) -> str:
    text = str(value or "")
    for marker in ("api_key=", "access_token=", "cookie=", "SESSDATA="):
        if marker.lower() in text.lower():
            return "[redacted]"
    return text


def request_deepseek_json(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from .compile_gateway import request_compile_json

    return request_compile_json(*args, provider="deepseek", **kwargs)

