from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DOCS_ASSETS_ROOT = REPO_ROOT / "docs" / "assets"
DEFAULT_STORE_ROOT = REPO_ROOT / "data" / "course-store"

sys.path.insert(0, str(REPO_ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "qa" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_guidance import get_learning_guide  # noqa: E402
from course2knowledge_lite_qa import answer_course_question  # noqa: E402
from course2knowledge_lite_store import LiteChatCore, SQLiteCourseStore  # noqa: E402


class Course2KnowledgeWebHandler(BaseHTTPRequestHandler):
    store_root = DEFAULT_STORE_ROOT

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self._send_static("index.html")
            elif parsed.path.startswith("/static/"):
                self._send_static(parsed.path.removeprefix("/static/"))
            elif parsed.path.startswith("/docs/assets/"):
                self._send_docs_asset(parsed.path.removeprefix("/docs/assets/"))
            elif parsed.path == "/api/courses":
                self._send_json({"courses": _list_courses(self.store_root)})
            elif parsed.path == "/api/lectures":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                self._send_json({"lectures": SQLiteCourseStore(self.store_root).read_lectures(course_id)})
            elif parsed.path == "/api/coverage":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                coverage = SQLiteCourseStore(self.store_root).summarize_transcript_coverage(course_id)
                self._send_json({"status": "completed", "coverage": coverage})
            elif parsed.path == "/api/reader":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                payload = SQLiteCourseStore(self.store_root).read_lecture_reader(
                    course_id,
                    lecture_sequence=_optional_param(params, "lecture_sequence"),
                    lecture_id=_optional_param(params, "lecture_id"),
                )
                self._send_json(payload)
            elif parsed.path == "/api/cards":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                cards = SQLiteCourseStore(self.store_root).list_knowledge_cards(course_id=course_id, lecture_id=lecture_id)
                self._send_json({"status": "completed", "course_id": course_id, "cards": cards, "card_count": len(cards)})
            elif parsed.path == "/api/search":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                query = _required_param(params, "query")
                hits = SQLiteCourseStore(self.store_root).search_transcripts(
                    course_id,
                    query,
                    limit=_limit(params, default=10),
                )
                self._send_json({"course_id": course_id, "query": query, "results": hits, "result_count": len(hits)})
            elif parsed.path == "/api/qa":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                question = _required_param(params, "question")
                payload = answer_course_question(
                    store=SQLiteCourseStore(self.store_root),
                    course_id=course_id,
                    question=question,
                    limit=_limit(params, default=5),
                )
                self._send_json(payload)
            elif parsed.path == "/api/guide":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                payload = get_learning_guide(
                    store=SQLiteCourseStore(self.store_root),
                    course_id=course_id,
                    mode=_optional_param(params, "mode") or "continue",
                    lecture_id=_optional_param(params, "lecture_id"),
                    lecture_sequence=_optional_param(params, "lecture_sequence") or None,
                    limit=_limit(params, default=3),
                )
                self._send_json(payload)
            elif parsed.path == "/api/notes":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                notes = SQLiteCourseStore(self.store_root).list_notes(course_id=course_id, lecture_id=lecture_id)
                self._send_json({"course_id": course_id, "notes": notes, "note_count": len(notes)})
            elif parsed.path == "/api/bookmarks":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                target_type = _optional_param(params, "target_type")
                bookmarks = SQLiteCourseStore(self.store_root).list_bookmarks(course_id=course_id, target_type=target_type)
                self._send_json(
                    {"course_id": course_id, "bookmarks": bookmarks, "bookmark_count": len(bookmarks)}
                )
            elif parsed.path == "/api/progress":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                store = SQLiteCourseStore(self.store_root)
                progress = [store.get_reading_progress(course_id, lecture_id)] if lecture_id else store.list_reading_progress(course_id=course_id)
                self._send_json({"course_id": course_id, "progress": progress, "progress_count": len(progress)})
            else:
                self.send_error(404, "Not found")
        except Exception as exc:  # noqa: BLE001
            self._send_json({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}, status=400)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json_body()
            store = SQLiteCourseStore(self.store_root)
            if parsed.path == "/api/notes":
                course_id = _required_body(payload, "course_id")
                note = store.create_note(
                    course_id,
                    _required_body(payload, "lecture_id"),
                    str(payload.get("body", "") or ""),
                )
                self._send_json({"status": "completed", "note": note}, status=201)
            elif parsed.path == "/api/bookmarks":
                bookmark = store.create_bookmark(
                    _required_body(payload, "course_id"),
                    _required_body(payload, "target_type"),
                    _required_body(payload, "target_id"),
                )
                self._send_json({"status": "completed", "bookmark": bookmark}, status=201)
            elif parsed.path == "/api/progress":
                progress = store.set_reading_progress(
                    _required_body(payload, "course_id"),
                    _required_body(payload, "lecture_id"),
                    _required_body(payload, "status"),
                )
                self._send_json({"status": "completed", "progress": progress}, status=201)
            elif parsed.path == "/api/cards/generate":
                result = store.generate_knowledge_cards(
                    _required_body(payload, "course_id"),
                    lecture_id=str(payload.get("lecture_id", "") or "").strip(),
                    overwrite=_bool_body(payload.get("overwrite"), default=True),
                )
                self._send_json({"status": "completed", **result}, status=201)
            elif parsed.path == "/api/chat/stream":
                result = LiteChatCore(store).run_turn(
                    course_id=_required_body(payload, "course_id"),
                    message=_required_body(payload, "message"),
                    thread_id=str(payload.get("thread_id", "") or "").strip(),
                    channel=str(payload.get("channel", "web") or "web").strip(),
                )
                self._send_sse(_chat_sse_events(result))
            elif parsed.path == "/api/import":
                result = import_collection_skeleton_to_store(
                    _required_body(payload, "source_url"),
                    store_root=self.store_root,
                )
                import_status = result.get("import_status") or {}
                self._send_json(
                    {
                        "status": "completed",
                        "course": result.get("course") or {},
                        "lecture_count": len(result.get("lectures") or []),
                        "import_status": import_status,
                        "paths": result.get("paths") or {},
                    },
                    status=201,
                )
            else:
                self.send_error(404, "Not found")
        except Exception as exc:  # noqa: BLE001
            self._send_json({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            params = parse_qs(parsed.query)
            store = SQLiteCourseStore(self.store_root)
            if parsed.path == "/api/courses":
                result = store.delete_course(_required_param(params, "course_id"))
                self._send_json({"status": "completed", **result})
            elif parsed.path == "/api/notes":
                result = store.delete_note(_required_param(params, "course_id"), _required_param(params, "note_id"))
                self._send_json({"status": "completed", **result})
            elif parsed.path == "/api/bookmarks":
                result = store.delete_bookmark(
                    _required_param(params, "course_id"),
                    _required_param(params, "bookmark_id"),
                )
                self._send_json({"status": "completed", **result})
            else:
                self.send_error(404, "Not found")
        except Exception as exc:  # noqa: BLE001
            self._send_json({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}, status=400)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, events: list[dict[str, Any]], *, status: int = 200) -> None:
        body = "".join(_encode_sse_event(event) for event in events).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, relative_path: str) -> None:
        path = (STATIC_ROOT / relative_path).resolve()
        if not _is_relative_to(path, STATIC_ROOT.resolve()) or not path.exists() or not path.is_file():
            self.send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_docs_asset(self, relative_path: str) -> None:
        path = (DOCS_ASSETS_ROOT / relative_path).resolve()
        if not _is_relative_to(path, DOCS_ASSETS_ROOT.resolve()) or not path.exists() or not path.is_file():
            self.send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw_body or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload


def _list_courses(store_root: Path) -> list[dict[str, Any]]:
    return SQLiteCourseStore(store_root).list_courses()


def _chat_sse_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    thread = dict(result.get("thread") or {})
    assistant_message = dict(result.get("assistant_message") or {})
    events: list[dict[str, Any]] = []
    for item in result.get("events") or []:
        event = dict(item)
        events.append(
            {
                "event": str(event.get("event_type") or "message"),
                "id": str(event.get("event_id") or ""),
                "data": _sanitize_chat_event_payload(
                    {
                        "event_id": str(event.get("event_id") or ""),
                        "event_type": str(event.get("event_type") or ""),
                        "thread_id": str(event.get("thread_id") or ""),
                        "message_id": str(event.get("message_id") or ""),
                        "tool_name": str(event.get("tool_name") or ""),
                        "payload": dict(event.get("payload") or {}),
                    }
                ),
            }
        )
    events.append(
        {
            "event": "thread_state",
            "id": str(assistant_message.get("message_id") or ""),
            "data": _sanitize_chat_event_payload(
                {
                    "status": str(result.get("status") or ""),
                    "route": str(result.get("route") or ""),
                    "thread": thread,
                    "assistant_message": assistant_message,
                }
            ),
        }
    )
    return events


def _encode_sse_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("event") or "message")
    event_id = str(event.get("id") or "")
    data = json.dumps(event.get("data") or {}, ensure_ascii=False, sort_keys=True)
    lines = [f"event: {event_type}"]
    if event_id:
        lines.append(f"id: {event_id}")
    lines.extend(f"data: {line}" for line in data.splitlines() or ["{}"])
    return "\n".join(lines) + "\n\n"


def _sanitize_chat_event_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_chat_event_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_chat_event_payload(item) for item in value]
    if isinstance(value, str):
        return _redact_raw_path(value)
    return value


def _redact_raw_path(value: str) -> str:
    parts = []
    for token in value.split():
        cleaned = token.strip(".,;:!?()[]{}\"'")
        path = Path(cleaned.replace("\\", "/"))
        is_windows_absolute = len(cleaned) >= 3 and cleaned[1:3] in {":/", ":\\"}
        if is_windows_absolute or path.is_absolute() or ".." in path.parts:
            parts.append(token.replace(cleaned, "[redacted-path]"))
        else:
            parts.append(token)
    return " ".join(parts)


def _required_param(params: dict[str, list[str]], name: str) -> str:
    value = _optional_param(params, name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _required_body(payload: dict[str, Any], name: str) -> str:
    value = str(payload.get(name, "") or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _optional_param(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name) or []
    return str(values[0] if values else "").strip()


def _limit(params: dict[str, list[str]], *, default: int) -> int:
    raw_value = _optional_param(params, "limit")
    if not raw_value:
        return default
    return max(int(raw_value), 0)


def _bool_body(raw_value: Any, *, default: bool) -> bool:
    if raw_value in (None, ""):
        return default
    if isinstance(raw_value, bool):
        return raw_value
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"boolean value expected: {raw_value}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Course2Knowledge Lite Web workspace.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3014)
    parser.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handler = Course2KnowledgeWebHandler
    handler.store_root = Path(args.store_root).expanduser().resolve()
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "serving",
                "url": f"http://{args.host}:{args.port}",
                "store_root": str(handler.store_root),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
