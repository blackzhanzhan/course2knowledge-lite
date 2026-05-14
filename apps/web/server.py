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
DEFAULT_STORE_ROOT = REPO_ROOT / "data" / "course-store"

sys.path.insert(0, str(REPO_ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "qa" / "src"))

from course2knowledge_lite_qa import answer_course_question  # noqa: E402
from course2knowledge_lite_store import JsonCourseStore  # noqa: E402


class Course2KnowledgeWebHandler(BaseHTTPRequestHandler):
    store_root = DEFAULT_STORE_ROOT

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self._send_static("index.html")
            elif parsed.path.startswith("/static/"):
                self._send_static(parsed.path.removeprefix("/static/"))
            elif parsed.path == "/api/courses":
                self._send_json({"courses": _list_courses(self.store_root)})
            elif parsed.path == "/api/lectures":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                self._send_json({"lectures": JsonCourseStore(self.store_root).read_lectures(course_id)})
            elif parsed.path == "/api/reader":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                payload = JsonCourseStore(self.store_root).read_lecture_reader(
                    course_id,
                    lecture_sequence=_optional_param(params, "lecture_sequence"),
                    lecture_id=_optional_param(params, "lecture_id"),
                )
                self._send_json(payload)
            elif parsed.path == "/api/search":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                query = _required_param(params, "query")
                hits = JsonCourseStore(self.store_root).search_transcripts(
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
                    store=JsonCourseStore(self.store_root),
                    course_id=course_id,
                    question=question,
                    limit=_limit(params, default=5),
                )
                self._send_json(payload)
            elif parsed.path == "/api/notes":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                notes = JsonCourseStore(self.store_root).list_notes(course_id=course_id, lecture_id=lecture_id)
                self._send_json({"course_id": course_id, "notes": notes, "note_count": len(notes)})
            elif parsed.path == "/api/bookmarks":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                target_type = _optional_param(params, "target_type")
                bookmarks = JsonCourseStore(self.store_root).list_bookmarks(course_id=course_id, target_type=target_type)
                self._send_json(
                    {"course_id": course_id, "bookmarks": bookmarks, "bookmark_count": len(bookmarks)}
                )
            elif parsed.path == "/api/progress":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                store = JsonCourseStore(self.store_root)
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
            store = JsonCourseStore(self.store_root)
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
            else:
                self.send_error(404, "Not found")
        except Exception as exc:  # noqa: BLE001
            self._send_json({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            params = parse_qs(parsed.query)
            store = JsonCourseStore(self.store_root)
            if parsed.path == "/api/notes":
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

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw_body or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload


def _list_courses(store_root: Path) -> list[dict[str, Any]]:
    courses_root = store_root / "courses"
    if not courses_root.exists():
        return []
    courses: list[dict[str, Any]] = []
    store = JsonCourseStore(store_root)
    for course_path in sorted(courses_root.glob("*/course.json")):
        course = store.read_course(course_path.parent.name)
        lectures = store.read_lectures(str(course.get("course_id") or course_path.parent.name))
        transcript_count = sum(
            1
            for lecture in lectures
            if store.read_transcript_segments_if_exists(
                str(course.get("course_id") or ""),
                str(lecture.get("lecture_id") or ""),
            )
        )
        courses.append(
            {
                **course,
                "lecture_count": len(lectures),
                "lecture_transcript_count": transcript_count,
            }
        )
    return courses


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
