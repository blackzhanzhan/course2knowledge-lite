from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_GATEWAY_URL = "http://127.0.0.1:8642/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 180


class HermesGatewayError(RuntimeError):
    """Raised when the live Hermes gateway cannot produce a turn."""


@dataclass(frozen=True)
class HermesGatewayReply:
    text: str
    session_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class HermesGatewayStreamEvent:
    event: str
    data: dict[str, Any]


def call_hermes_gateway(
    *,
    message: str,
    system_prompt: str,
    session_key: str,
    session_id: str = "",
    gateway_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> HermesGatewayReply:
    """Call the live Hermes API-server gateway and return assistant text."""

    user_message = " ".join(str(message or "").split())
    if not user_message:
        raise ValueError("message is required")

    url = (gateway_url or os.getenv("HERMES_WEB_GATEWAY_URL") or DEFAULT_GATEWAY_URL).strip()
    key = api_key if api_key is not None else os.getenv("HERMES_WEB_GATEWAY_API_KEY", "")
    payload = {
        "model": "hermes-agent",
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
        headers["X-Hermes-Session-Key"] = _safe_header_value(session_key)[:512]
        if session_id:
            headers["X-Hermes-Session-Id"] = _safe_header_value(session_id)[:512]

    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
            response_session_id = response.headers.get("X-Hermes-Session-Id", "")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HermesGatewayError(_gateway_error_message(exc.code, body)) from exc
    except URLError as exc:
        raise HermesGatewayError(f"Hermes gateway is unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HermesGatewayError("Hermes gateway timed out before returning a reply.") from exc
    except OSError as exc:
        raise HermesGatewayError(f"Hermes gateway connection failed: {exc}") from exc

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HermesGatewayError("Hermes gateway returned non-JSON response.") from exc
    if not isinstance(data, dict):
        raise HermesGatewayError("Hermes gateway returned an invalid response shape.")

    assistant_text = _extract_chat_completion_text(data)
    if not assistant_text:
        raise HermesGatewayError("Hermes gateway returned no assistant text.")
    return HermesGatewayReply(text=assistant_text, session_id=response_session_id, raw=data)


def stream_hermes_gateway(
    *,
    message: str,
    system_prompt: str,
    session_key: str,
    session_id: str = "",
    gateway_url: str | None = None,
    api_key: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Iterator[dict[str, Any]]:
    """Stream assistant deltas from the live Hermes API-server gateway."""

    user_message = " ".join(str(message or "").split())
    if not user_message:
        raise ValueError("message is required")

    url = (gateway_url or os.getenv("HERMES_WEB_GATEWAY_URL") or DEFAULT_GATEWAY_URL).strip()
    key = api_key if api_key is not None else os.getenv("HERMES_WEB_GATEWAY_API_KEY", "")
    payload = {
        "model": "hermes-agent",
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
        headers["X-Hermes-Session-Key"] = _safe_header_value(session_key)[:512]
        if session_id:
            headers["X-Hermes-Session-Id"] = _safe_header_value(session_id)[:512]

    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_session_id = response.headers.get("X-Hermes-Session-Id", "")
            yielded_text = False
            for event in _iter_sse_events(response):
                if event.event == "hermes.tool.progress":
                    yield {
                        "type": "tool_progress",
                        "payload": dict(event.data),
                        "session_id": response_session_id,
                    }
                    continue
                delta = _extract_chat_completion_delta(event.data)
                if delta:
                    yielded_text = True
                    yield {"type": "delta", "delta": delta, "session_id": response_session_id}
            yield {"type": "done", "session_id": response_session_id, "had_text": yielded_text}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HermesGatewayError(_gateway_error_message(exc.code, body)) from exc
    except URLError as exc:
        raise HermesGatewayError(f"Hermes gateway is unreachable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HermesGatewayError("Hermes gateway timed out before returning a reply.") from exc
    except OSError as exc:
        raise HermesGatewayError(f"Hermes gateway connection failed: {exc}") from exc


def _extract_chat_completion_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return ""


def _extract_chat_completion_delta(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text") or item.get("content") or "") for item in content if isinstance(item, dict))
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return str(message.get("content") or "")
    text = first.get("text")
    return str(text or "") if text else ""


def _iter_sse_events(response: Any) -> Iterator[HermesGatewayStreamEvent]:
    event_lines: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            yield from _flush_sse_event(event_lines)
            event_lines = []
            continue
        event_lines.append(line)
    yield from _flush_sse_event(event_lines)


def _flush_sse_event(lines: list[str]) -> Iterator[HermesGatewayStreamEvent]:
    if not lines:
        return
    event_type = "message"
    data_parts: list[str] = []
    for line in lines:
        if line.startswith("event:"):
            event_type = line[6:].lstrip() or "message"
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
    if not data_parts:
        return
    data = "\n".join(data_parts).strip()
    if not data or data == "[DONE]":
        return
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return
    if isinstance(payload, dict):
        yield HermesGatewayStreamEvent(event=event_type, data=payload)


def _gateway_error_message(status_code: int, body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return f"Hermes gateway HTTP {status_code}: {error['message']}"
    cleaned = " ".join(str(body or "").split())
    suffix = f": {cleaned[:300]}" if cleaned else ""
    return f"Hermes gateway HTTP {status_code}{suffix}"


def _safe_header_value(value: str) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("\x00", " ").strip()
