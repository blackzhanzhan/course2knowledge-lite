from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import threading
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


SERVER_STARTED_AT = datetime.now(timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DOCS_ASSETS_ROOT = REPO_ROOT / "docs" / "assets"
DEFAULT_STORE_ROOT = REPO_ROOT / "data" / "course-store"
DEFAULT_IMPORT_LECTURE_WORKERS = 10
DEFAULT_IMPORT_DOSSIER_CHUNK_WORKERS = 8
DEFAULT_IMPORT_DOSSIER_REQUEST_CONCURRENCY = 80
PUBLIC_DEMO_ENV = "COURSE2KNOWLEDGE_LITE_PUBLIC_DEMO"
BILIBILI_AUTH_FILE = REPO_ROOT / ".codex" / "auth" / "bilibili.json"
BILIBILI_QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
BILIBILI_QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
BILIBILI_QR_SESSION_TTL_SECONDS = 180
BILIBILI_QR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

sys.path.insert(0, str(REPO_ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "qa" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_bilibili import (  # noqa: E402
    build_bilibili_json_fetcher,
    import_collection_pipeline_to_store,
    redact_bilibili_cookie,
)
from course2knowledge_lite_guidance import get_learning_guide  # noqa: E402
from course2knowledge_lite_qa import answer_course_question  # noqa: E402
from course2knowledge_lite_store import SQLiteCourseStore  # noqa: E402

try:
    from course2knowledge_lite_store.web_hermes import (  # noqa: E402
        build_web_hermes_sse_events,
        build_web_hermes_turn,
        stream_web_hermes_sse_events,
    )
except Exception:  # noqa: BLE001
    build_web_hermes_sse_events = None
    build_web_hermes_turn = None
    stream_web_hermes_sse_events = None


class BilibiliQrLoginSession:
    def __init__(
        self,
        *,
        login_id: str,
        qrcode_key: str,
        qr_url: str,
        created_at: datetime,
        expires_at: datetime,
        cookie_jar: CookieJar | None = None,
    ) -> None:
        self.login_id = login_id
        self.qrcode_key = qrcode_key
        self.qr_url = qr_url
        self.created_at = created_at
        self.expires_at = expires_at
        self.cookie_jar = cookie_jar or CookieJar()
        self.status = "pending"
        self.message = "等待扫码"
        self.cookie_header = ""


_BILIBILI_QR_SESSIONS: dict[str, BilibiliQrLoginSession] = {}
_BILIBILI_QR_LOCK = threading.Lock()
_BILIBILI_AUTH_LOCK = threading.Lock()
_IMPORT_TEMP_STORES: dict[str, Path] = {}
_IMPORT_TEMP_STORES_LOCK = threading.Lock()


class Course2KnowledgeWebHandler(BaseHTTPRequestHandler):
    store_root = DEFAULT_STORE_ROOT
    public_demo = False

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
            elif parsed.path == "/api/runtime":
                self._send_json(
                    {
                        "status": "completed",
                        "runtime": {
                            "public_demo": _is_public_demo(),
                            "mutable_course_store": not _is_public_demo(),
                        },
                    }
                )
            elif parsed.path == "/api/lectures":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                self._send_json({"lectures": SQLiteCourseStore(self.store_root).read_lectures(course_id)})
            elif parsed.path == "/api/coverage":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                coverage = SQLiteCourseStore(self.store_root).summarize_transcript_coverage(course_id)
                self._send_json({"status": "completed", "coverage": coverage})
            elif parsed.path == "/api/import/status":
                params = parse_qs(parsed.query)
                store = SQLiteCourseStore(self.store_root)
                run_id = _optional_param(params, "run_id")
                course_id = _optional_param(params, "course_id")
                if run_id:
                    run = store.read_import_run(run_id)
                    raw_events = store.list_import_events(run_id)
                    events = [_public_import_event(event) for event in raw_events]
                    progress = _temp_import_status_payload(self.store_root, run_id)
                    promotion = _latest_promotion_payload(raw_events) or _latest_temp_import_payload(raw_events)
                    if progress.get("available") and not promotion.get("candidate"):
                        promotion["candidate"] = progress.get("readiness") if isinstance(progress.get("readiness"), dict) else {}
                    readiness = _readiness_for_import_status(store, run, raw_events)
                    if not readiness.get("lecture_count") and isinstance(progress.get("readiness"), dict):
                        readiness = dict(progress["readiness"])
                    self._send_json(
                        {
                            "status": "completed",
                            "run": run,
                            "events": events,
                            "artifacts": store.list_import_artifacts(run_id=run_id),
                            "readiness": readiness,
                            "promotion": _public_promotion_payload(promotion),
                            "progress": progress,
                        }
                    )
                elif course_id:
                    runs = store.list_import_runs(course_id=course_id)
                    if not runs:
                        store.backfill_import_run_from_readiness(course_id)
                        runs = store.list_import_runs(course_id=course_id)
                    self._send_json(
                        {
                            "status": "completed",
                            "runs": runs,
                            "readiness": store.summarize_import_readiness(course_id),
                        }
                    )
                else:
                    self._send_json({"status": "completed", "runs": store.list_import_runs()})
            elif parsed.path == "/api/readiness":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                self._send_json(
                    {
                        "status": "completed",
                        "readiness": SQLiteCourseStore(self.store_root).summarize_import_readiness(course_id),
                    }
                )
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
            elif parsed.path == "/api/visuals":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                lecture_id = _optional_param(params, "lecture_id")
                visuals = SQLiteCourseStore(self.store_root).list_visual_evidence(
                    course_id=course_id,
                    lecture_id=lecture_id,
                    query=_optional_param(params, "query"),
                )
                self._send_json({"course_id": course_id, "visuals": visuals, "visual_count": len(visuals)})
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
            elif parsed.path == "/api/chat/history":
                params = parse_qs(parsed.query)
                course_id = _required_param(params, "course_id")
                thread_id = _optional_param(params, "thread_id")
                self._send_json(_chat_history_payload(SQLiteCourseStore(self.store_root), course_id=course_id, thread_id=thread_id))
            elif parsed.path == "/api/bilibili/cookie":
                self._send_json({"status": "completed", "auth": _bilibili_cookie_status()})
            elif parsed.path == "/api/bilibili/login/qrcode/status":
                params = parse_qs(parsed.query)
                login_id = _required_param(params, "login_id")
                self._send_json(_poll_bilibili_qr_login(login_id))
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
                _require_mutable_endpoint("saving notes")
                course_id = _required_body(payload, "course_id")
                note = store.create_note(
                    course_id,
                    _required_body(payload, "lecture_id"),
                    str(payload.get("body", "") or ""),
                )
                self._send_json({"status": "completed", "note": note}, status=201)
            elif parsed.path == "/api/bilibili/login/qrcode":
                _require_mutable_endpoint("Bilibili QR login")
                self._send_json(_start_bilibili_qr_login(), status=201)
            elif parsed.path == "/api/bilibili/login/qrcode/clear":
                _require_mutable_endpoint("Bilibili QR login")
                login_id = _required_body(payload, "login_id")
                self._send_json(_clear_bilibili_qr_login(login_id))
            elif parsed.path == "/api/bilibili/cookie/save":
                _require_mutable_endpoint("Bilibili cookie storage")
                bilibili_cookie = str(payload.get("bilibili_cookie", "") or "").strip()
                qr_login_id = str(payload.get("bilibili_qr_login_id", "") or "").strip()
                if qr_login_id and not bilibili_cookie:
                    bilibili_cookie = _consume_bilibili_qr_cookie(qr_login_id)
                if not bilibili_cookie:
                    raise ValueError("bilibili_cookie or a completed bilibili_qr_login_id is required")
                _save_persisted_bilibili_cookie(bilibili_cookie)
                self._send_json({"status": "completed", "auth": _bilibili_cookie_status()}, status=201)
            elif parsed.path == "/api/bilibili/cookie/clear":
                _require_mutable_endpoint("Bilibili cookie storage")
                _clear_persisted_bilibili_cookie()
                self._send_json({"status": "completed", "auth": _bilibili_cookie_status()})
            elif parsed.path == "/api/bookmarks":
                _require_mutable_endpoint("saving bookmarks")
                bookmark = store.create_bookmark(
                    _required_body(payload, "course_id"),
                    _required_body(payload, "target_type"),
                    _required_body(payload, "target_id"),
                )
                self._send_json({"status": "completed", "bookmark": bookmark}, status=201)
            elif parsed.path == "/api/progress":
                _require_mutable_endpoint("saving reading progress")
                progress = store.set_reading_progress(
                    _required_body(payload, "course_id"),
                    _required_body(payload, "lecture_id"),
                    _required_body(payload, "status"),
                )
                self._send_json({"status": "completed", "progress": progress}, status=201)
            elif parsed.path == "/api/cards/generate":
                _require_mutable_endpoint("generating knowledge cards")
                result = store.generate_knowledge_cards(
                    _required_body(payload, "course_id"),
                    lecture_id=str(payload.get("lecture_id", "") or "").strip(),
                    overwrite=_bool_body(payload.get("overwrite"), default=True),
                    compile_mode=str(payload.get("compile_mode", "model") or "model").strip(),
                    compile_provider=str(payload.get("compile_provider", "deepseek") or "").strip() or None,
                    model=str(payload.get("model", "") or "").strip() or None,
                    max_chunk_workers=max(1, int(payload.get("max_chunk_workers", 1) or 1)),
                    max_concurrent_requests=max(1, int(payload.get("max_concurrent_requests", 1) or 1)),
                    fast_map_mode=_bool_body(payload.get("fast_map_mode"), default=True),
                    split_map_mode=_bool_body(payload.get("split_map_mode"), default=True),
                    fast_reduce_mode=_bool_body(payload.get("fast_reduce_mode"), default=True),
                    lite_map_mode=_bool_body(payload.get("lite_map_mode"), default=False),
                )
                self._send_json({"status": "completed", **result}, status=201)
            elif parsed.path == "/api/chat/stream":
                course_id = _required_body(payload, "course_id")
                course = store.read_course(course_id)
                lecture_id = str(payload.get("lecture_id", "") or "").strip()
                lecture_sequence = str(payload.get("lecture_sequence", "") or "").strip()
                message = _required_body(payload, "message")
                channel = str(payload.get("channel", "web") or "web").strip()
                thread = _chat_thread_for_stream(
                    store,
                    course_id=course_id,
                    message=message,
                    thread_id=str(payload.get("thread_id", "") or "").strip(),
                    channel=channel,
                )
                if _is_visual_request(message):
                    selected_lecture = _select_context_lecture(
                        store.read_lectures(course_id),
                        lecture_id=lecture_id,
                        lecture_sequence=lecture_sequence,
                    )
                    events = _build_visual_sse_events(
                        store=store,
                        course_id=course_id,
                        lecture_id=str(selected_lecture.get("lecture_id") or lecture_id),
                        message=message,
                    )
                    persistent_events = _persist_hermes_stream_events(
                        store,
                        thread=thread,
                        user_message=message,
                        events=events,
                    )
                    self._send_sse_stream(persistent_events)
                    return
                if stream_web_hermes_sse_events is None:
                    raise RuntimeError("Hermes Web frontdesk adapter is unavailable")
                binding = store.get_web_course_binding(course_id)
                binding["child_course_title"] = str(course.get("title", "") or "")
                course_context = _build_web_course_context(
                    store=store,
                    course_id=course_id,
                    course=course,
                    lecture_id=lecture_id,
                    lecture_sequence=lecture_sequence,
                )
                history_messages = store.list_chat_messages(str(thread.get("thread_id") or ""))
                history_events = store.list_chat_events(str(thread.get("thread_id") or ""))
                chat_messages_for_control = [
                    *history_messages,
                    {"role": "user", "content": message},
                ]
                events = stream_web_hermes_sse_events(
                    message=message,
                    thread_id=str(thread.get("thread_id") or ""),
                    channel=channel,
                    web_course_id=course_id,
                    course_binding=binding,
                    course_context=course_context,
                    chat_messages=chat_messages_for_control,
                    chat_events=history_events,
                )
                persistent_events = _persist_hermes_stream_events(
                    store,
                    thread=thread,
                    user_message=message,
                    events=events,
                )
                self._send_sse_stream(persistent_events)
            elif parsed.path == "/api/import":
                _require_mutable_endpoint("importing courses")
                source_url = _required_body(payload, "source_url")
                bilibili_cookie = str(payload.get("bilibili_cookie", "") or "").strip()
                qr_login_id = str(payload.get("bilibili_qr_login_id", "") or "").strip()
                qr_cookie = _consume_bilibili_qr_cookie(qr_login_id) if qr_login_id and not bilibili_cookie else ""
                stored_cookie = _load_persisted_bilibili_cookie() if not bilibili_cookie and not qr_cookie else ""
                effective_bilibili_cookie = bilibili_cookie or qr_cookie or stored_cookie
                remember_cookie = _bool_body(payload.get("remember_bilibili_cookie"), default=False)
                if remember_cookie and (bilibili_cookie or qr_cookie):
                    _save_persisted_bilibili_cookie(bilibili_cookie or qr_cookie)
                auth_source = (
                    "manual_cookie"
                    if bilibili_cookie
                    else ("qr_login" if qr_cookie else ("stored_cookie" if stored_cookie else "none"))
                )
                run = store.create_import_run(
                    course_id="",
                    source_url=source_url,
                    source_platform="bilibili",
                    status="queued",
                    stage="queued",
                )
                store.append_import_event(
                    str(run["run_id"]),
                    stage="queued",
                    status="queued",
                    event_type="import_requested",
                    message=(
                        "Import queued from Web Lite. Bilibili cookie was saved locally for reuse."
                        if remember_cookie and (bilibili_cookie or qr_cookie)
                        else "Import queued from Web Lite. Bilibili cookie values are never exposed in responses."
                    ),
                    payload={
                        "source_url": source_url,
                        "cookie_present": bool(effective_bilibili_cookie),
                        "auth_source": auth_source,
                        "remember_cookie": bool(remember_cookie and (bilibili_cookie or qr_cookie)),
                        "stored_cookie_available": bool(stored_cookie),
                        "promotion_policy": "backup_then_merge_new_or_replace_same_course_if_readiness_not_worse",
                    },
                )
                _start_import_worker(
                    run_id=str(run["run_id"]),
                    source_url=source_url,
                    store_root=self.store_root,
                    fetch_transcripts=_bool_body(payload.get("fetch_transcripts"), default=True),
                    bilibili_cookie=effective_bilibili_cookie,
                    max_lectures=_optional_positive_int_body(payload.get("max_lectures")),
                    compile_mode=str(payload.get("compile_mode", "model") or "model").strip(),
                    compile_provider=str(payload.get("compile_provider", "deepseek") or "").strip() or None,
                    model=str(payload.get("model", "") or "").strip() or None,
                    max_chunk_workers=max(
                        1,
                        int(payload.get("max_chunk_workers", DEFAULT_IMPORT_DOSSIER_CHUNK_WORKERS) or DEFAULT_IMPORT_DOSSIER_CHUNK_WORKERS),
                    ),
                    max_concurrent_requests=max(
                        1,
                        int(payload.get("max_concurrent_requests", DEFAULT_IMPORT_DOSSIER_REQUEST_CONCURRENCY) or DEFAULT_IMPORT_DOSSIER_REQUEST_CONCURRENCY),
                    ),
                    lecture_workers=max(
                        1,
                        int(payload.get("lecture_workers", DEFAULT_IMPORT_LECTURE_WORKERS) or DEFAULT_IMPORT_LECTURE_WORKERS),
                    ),
                    fast_map_mode=_bool_body(payload.get("fast_map_mode"), default=True),
                    split_map_mode=_bool_body(payload.get("split_map_mode"), default=True),
                    fast_reduce_mode=_bool_body(payload.get("fast_reduce_mode"), default=True),
                    lite_map_mode=_bool_body(payload.get("lite_map_mode"), default=False),
                )
                self._send_json(
                    {
                        "status": "accepted",
                        "run_id": run.get("run_id") or "",
                        "run": run,
                        "course": {},
                        "lecture_count": 0,
                        "import_status": {},
                        "readiness": {},
                        "paths": {},
                    },
                    status=201,
                )
            elif parsed.path == "/api/import/cancel":
                _require_mutable_endpoint("import management")
                run_id = _required_body(payload, "run_id")
                run = _cancel_import_run_everywhere(self.store_root, run_id)
                self._send_json({"status": "completed", "run": run})
            elif parsed.path == "/api/import/retry-failed":
                _require_mutable_endpoint("import management")
                run_id = _required_body(payload, "run_id")
                previous_run = store.read_import_run(run_id)
                course_id = str(previous_run.get("course_id") or "").strip()
                if not course_id:
                    raise ValueError("cannot retry an import run before course skeleton exists")
                course = store.read_course(course_id)
                retry_run = store.create_import_run(
                    course_id=course_id,
                    source_url=str(course.get("source_url") or previous_run.get("source_url") or ""),
                    source_platform=str(course.get("source_platform") or previous_run.get("source_platform") or "bilibili"),
                    status="queued",
                    stage="retry_failed_lessons",
                    total_lectures=int(previous_run.get("total_lectures") or 0),
                )
                store.append_import_event(
                    str(retry_run["run_id"]),
                    stage="retry_failed_lessons",
                    status="queued",
                    event_type="retry_requested",
                    message="Retry failed lessons requested from Web Lite.",
                    payload={
                        "previous_run_id": run_id,
                        "auth_source": "manual_cookie" if str(payload.get("bilibili_cookie", "") or "").strip() else "none",
                    },
                )
                _start_import_worker(
                    run_id=str(retry_run["run_id"]),
                    source_url=str(retry_run["source_url"] or ""),
                    store_root=self.store_root,
                    fetch_transcripts=_bool_body(payload.get("fetch_transcripts"), default=True),
                    bilibili_cookie=str(payload.get("bilibili_cookie", "") or "").strip(),
                    compile_mode=str(payload.get("compile_mode", "model") or "model").strip(),
                    compile_provider=str(payload.get("compile_provider", "deepseek") or "").strip() or None,
                    model=str(payload.get("model", "") or "").strip() or None,
                    max_chunk_workers=max(1, int(payload.get("max_chunk_workers", 1) or 1)),
                    max_concurrent_requests=max(1, int(payload.get("max_concurrent_requests", 1) or 1)),
                    fast_map_mode=_bool_body(payload.get("fast_map_mode"), default=True),
                    split_map_mode=_bool_body(payload.get("split_map_mode"), default=True),
                    fast_reduce_mode=_bool_body(payload.get("fast_reduce_mode"), default=True),
                    lite_map_mode=_bool_body(payload.get("lite_map_mode"), default=False),
                )
                self._send_json({"status": "accepted", "run_id": retry_run["run_id"], "run": retry_run}, status=202)
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
                _require_mutable_endpoint("deleting courses")
                result = store.delete_course(_required_param(params, "course_id"))
                self._send_json({"status": "completed", **result})
            elif parsed.path == "/api/notes":
                _require_mutable_endpoint("deleting notes")
                result = store.delete_note(_required_param(params, "course_id"), _required_param(params, "note_id"))
                self._send_json({"status": "completed", **result})
            elif parsed.path == "/api/bookmarks":
                _require_mutable_endpoint("deleting bookmarks")
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

    def _send_sse_stream(self, events: Any, *, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        for event in events:
            self.wfile.write(_encode_sse_event(event).encode("utf-8"))
            self.wfile.flush()

    def _send_static(self, relative_path: str) -> None:
        path = (STATIC_ROOT / relative_path).resolve()
        if not _is_relative_to(path, STATIC_ROOT.resolve()) or not path.exists() or not path.is_file():
            self.send_error(404, "Not found")
            return
        content_type = _content_type_for_path(path)
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
        content_type = _content_type_for_path(path)
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


def _is_public_demo() -> bool:
    return bool(Course2KnowledgeWebHandler.public_demo or _bool_env(PUBLIC_DEMO_ENV))


def _bool_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _require_mutable_endpoint(action: str) -> None:
    if _is_public_demo():
        raise PermissionError(f"public demo mode is read-only; {action} is disabled")


def _content_type_for_path(path: Path) -> str:
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    if content_type in {"text/html", "text/css", "text/javascript", "application/javascript"}:
        return f"{content_type}; charset=utf-8"
    return content_type


def _remember_temp_import_store(run_id: str, store_root: Path) -> None:
    with _IMPORT_TEMP_STORES_LOCK:
        _IMPORT_TEMP_STORES[str(run_id)] = Path(store_root)


def _forget_temp_import_store(run_id: str) -> None:
    with _IMPORT_TEMP_STORES_LOCK:
        _IMPORT_TEMP_STORES.pop(str(run_id), None)


def _temp_store_root_for_run(store_root: Path, run_id: str) -> tuple[Path | None, bool]:
    with _IMPORT_TEMP_STORES_LOCK:
        temp_root = _IMPORT_TEMP_STORES.get(str(run_id))
    if temp_root:
        return Path(temp_root), False
    temp_root = _latest_temp_store_root(store_root, run_id)
    return (temp_root, True) if temp_root else (None, False)


def _cancel_import_run_everywhere(store_root: Path, run_id: str) -> dict[str, Any]:
    production_store = SQLiteCourseStore(store_root)
    run = production_store.update_import_run(run_id, status="cancelled", stage="cancelled")
    production_store.append_import_event(
        run_id,
        stage="cancelled",
        status="cancelled",
        event_type="cancel_requested",
        message="Cancel requested from Web Lite.",
        payload={},
    )
    temp_root, _from_disk = _temp_store_root_for_run(store_root, run_id)
    if temp_root:
        try:
            temp_store = SQLiteCourseStore(temp_root)
            temp_store.update_import_run(run_id, status="cancelled", stage="cancelled")
            temp_store.append_import_event(
                run_id,
                stage="cancelled",
                status="cancelled",
                event_type="cancel_requested",
                message="Cancel requested from Web Lite.",
                payload={},
            )
        except Exception:
            pass
    return run


def _temp_import_status_payload(store_root: Path, run_id: str) -> dict[str, Any]:
    temp_root, from_disk = _temp_store_root_for_run(store_root, run_id)
    if not temp_root:
        return {"available": False}
    try:
        temp_store = SQLiteCourseStore(temp_root)
        run = temp_store.read_import_run(run_id)
        events = [_public_import_event(event) for event in temp_store.list_import_events(run_id)]
        if (
            from_disk
            and str(run.get("status") or "") == "running"
            and _run_updated_before_server_start(run)
            and _path_modified_before_server_start(temp_root)
        ):
            run = {
                **run,
                "status": "failed",
                "stage": "interrupted",
            }
            events = [
                *events,
                {
                    "event_id": "",
                    "run_id": run_id,
                    "event_index": len(events) + 1,
                    "stage": "interrupted",
                    "status": "failed",
                    "event_type": "run_interrupted",
                    "message": "服务重启后旧导入任务已中断，请重新导入以使用并发管线。",
                    "payload": {"error_type": "InterruptedImportRun"},
                    "created_at": "",
                },
            ]
        readiness = _readiness_for_import_status(temp_store, run, events)
        artifacts = temp_store.list_import_artifacts(run_id=run_id)
        return {
            "available": True,
            "stale": bool(from_disk and str(run.get("stage") or "") == "interrupted"),
            "run": _public_import_run(run),
            "events": events,
            "readiness": _compact_readiness(readiness),
            "artifact_summary": _artifact_status_summary(artifacts),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "error_type": type(exc).__name__,
            "error": _redact_secret(str(exc)),
        }


def _run_updated_before_server_start(run: dict[str, Any]) -> bool:
    updated_at = str(run.get("updated_at") or run.get("created_at") or "").strip()
    if not updated_at:
        return True
    try:
        parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed < (SERVER_STARTED_AT - timedelta(seconds=2))


def _path_modified_before_server_start(path: Path) -> bool:
    try:
        modified_at = datetime.fromtimestamp(Path(path).stat().st_mtime, tz=timezone.utc)
    except OSError:
        return True
    return modified_at < (SERVER_STARTED_AT - timedelta(seconds=2))


def _latest_temp_store_root(store_root: Path, run_id: str) -> Path | None:
    parent = store_root / "tmp" / "guarded-reimports"
    if not parent.exists():
        return None
    candidates = [path for path in parent.glob(f"{run_id}_*") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _public_import_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: run.get(key)
        for key in (
            "run_id",
            "course_id",
            "source_url",
            "source_platform",
            "status",
            "stage",
            "total_lectures",
            "completed_lectures",
            "failed_lectures",
            "created_at",
            "updated_at",
        )
    }


def _public_import_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return {
        "event_id": event.get("event_id"),
        "run_id": event.get("run_id"),
        "event_index": event.get("event_index"),
        "stage": event.get("stage"),
        "status": event.get("status"),
        "event_type": event.get("event_type"),
        "message": _redact_secret(str(event.get("message") or "")),
        "payload": _public_import_event_payload(payload),
        "created_at": event.get("created_at"),
    }


def _public_import_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "course_id",
        "lecture_count",
        "lecture_id",
        "segment_count",
        "ready",
        "ready_lecture_count",
        "missing_lecture_count",
        "error_type",
        "error",
        "missing",
        "requested_parallelism",
        "effective_parallelism",
        "parallelism",
        "parallelism_profile",
        "parallelism_guard",
        "selected_lecture_count",
        "source_kind",
        "cookie_present",
        "auth_source",
        "remember_cookie",
        "stored_cookie_available",
    }
    result: dict[str, Any] = {}
    for key in allowed_keys:
        if key in payload:
            result[key] = _redact_secret(str(payload[key])) if key in {"error"} else payload[key]
    return result


def _artifact_status_summary(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": len(artifacts), "by_type": {}, "failed": 0}
    by_type: dict[str, dict[str, int]] = {}
    for artifact in artifacts:
        artifact_type = str(artifact.get("artifact_type") or "unknown")
        status = str(artifact.get("status") or "unknown")
        bucket = by_type.setdefault(artifact_type, {})
        bucket[status] = bucket.get(status, 0) + 1
        if status == "failed":
            summary["failed"] = int(summary["failed"]) + 1
    summary["by_type"] = by_type
    return summary


def _public_promotion_payload(promotion: dict[str, Any]) -> dict[str, Any]:
    payload = dict(promotion or {})
    payload.pop("backup_path", None)
    payload.pop("temp_store_root", None)
    previous = payload.get("previous")
    if isinstance(previous, dict):
        payload["previous"] = {
            "course_count": int(previous.get("course_count") or 0),
            "best": _compact_readiness(previous.get("best") if isinstance(previous.get("best"), dict) else {}),
        }
    candidate = payload.get("candidate")
    if isinstance(candidate, dict):
        payload["candidate"] = _compact_readiness(candidate)
    return payload


def _start_import_worker(
    *,
    run_id: str,
    source_url: str,
    store_root: Path,
    fetch_transcripts: bool,
    bilibili_cookie: str = "",
    max_lectures: int | None = None,
    compile_mode: str = "model",
    compile_provider: str | None = "deepseek",
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    lecture_workers: int = 1,
    fast_map_mode: bool = True,
    split_map_mode: bool = True,
    fast_reduce_mode: bool = True,
    lite_map_mode: bool = False,
) -> None:
    def _target() -> None:
        worker_store = SQLiteCourseStore(store_root)
        try:
            _run_guarded_reimport(
                run_id=run_id,
                source_url=source_url,
                store_root=Path(store_root),
                fetch_transcripts=fetch_transcripts,
                bilibili_cookie=bilibili_cookie,
                max_lectures=max_lectures,
                compile_mode=compile_mode,
                compile_provider=compile_provider,
                model=model,
                max_chunk_workers=max_chunk_workers,
                max_concurrent_requests=max_concurrent_requests,
                lecture_workers=lecture_workers,
                fast_map_mode=fast_map_mode,
                split_map_mode=split_map_mode,
                fast_reduce_mode=fast_reduce_mode,
                lite_map_mode=lite_map_mode,
            )
        except Exception as exc:  # noqa: BLE001
            message = _redact_secret(str(exc), bilibili_cookie)
            try:
                worker_store.update_import_run(run_id, status="failed", stage="failed")
                worker_store.append_import_event(
                    run_id,
                    stage="failed",
                    status="failed",
                    event_type="worker_failed",
                    message=message,
                    payload={"error_type": type(exc).__name__},
                )
            except Exception:
                return

    thread = threading.Thread(target=_target, name=f"lite-import-{run_id}", daemon=True)
    thread.start()


def _run_guarded_reimport(
    *,
    run_id: str,
    source_url: str,
    store_root: Path,
    fetch_transcripts: bool,
    bilibili_cookie: str = "",
    max_lectures: int | None = None,
    compile_mode: str = "model",
    compile_provider: str | None = "deepseek",
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    lecture_workers: int = 1,
    fast_map_mode: bool = True,
    split_map_mode: bool = True,
    fast_reduce_mode: bool = True,
    lite_map_mode: bool = False,
) -> dict[str, Any]:
    production_store = SQLiteCourseStore(store_root)
    production_snapshot = _store_readiness_snapshot(production_store)
    production_store.update_import_run(run_id, status="running", stage="temp_import")
    production_store.append_import_event(
        run_id,
        stage="temp_import",
        status="running",
        event_type="temp_import_started",
        message="Importing into a temporary SQLite store before any overwrite.",
        payload={
            "previous": _compact_readiness_snapshot(production_snapshot),
            "cookie_present": bool(str(bilibili_cookie or "").strip()),
            "compile_mode": compile_mode,
            "compile_provider": compile_provider or "",
            "model": model or "",
            "parallelism": {
                "lecture_workers": int(lecture_workers or 1),
                "dossier_chunk_workers": int(max_chunk_workers or 1),
                "dossier_request_concurrency": int(max_concurrent_requests or 1),
            },
        },
    )

    tmp_parent = store_root / "tmp" / "guarded-reimports"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    temp_store_root = Path(tempfile.mkdtemp(prefix=f"{run_id}_", dir=tmp_parent))
    _remember_temp_import_store(run_id, temp_store_root)
    SQLiteCourseStore(temp_store_root).create_import_run(
        run_id=run_id,
        course_id="",
        source_url=source_url,
        source_platform="bilibili",
        status="queued",
        stage="queued",
    )
    fetch_json = build_bilibili_json_fetcher(cookie=bilibili_cookie) if str(bilibili_cookie or "").strip() else None
    try:
        temp_result = import_collection_pipeline_to_store(
            source_url,
            store_root=temp_store_root,
            run_id=run_id,
            fetch_transcripts=fetch_transcripts,
            fetch_json=fetch_json,
            max_lectures=max_lectures,
            compile_mode=compile_mode,
            compile_provider=compile_provider,
            model=model,
            max_chunk_workers=max_chunk_workers,
            max_concurrent_requests=max_concurrent_requests,
            lecture_workers=lecture_workers,
            apply_parallelism_profile=True,
            source_kind="bilibili_native_subtitle_pending",
            fast_map_mode=fast_map_mode,
            split_map_mode=split_map_mode,
            fast_reduce_mode=fast_reduce_mode,
            lite_map_mode=lite_map_mode,
        )
        temp_store = SQLiteCourseStore(temp_store_root)
        temp_course_id = str((temp_result.get("course") or {}).get("course_id") or "")
        temp_readiness = temp_store.summarize_import_readiness(temp_course_id) if temp_course_id else {}
        decision = _promotion_decision(
            production_snapshot,
            temp_readiness,
            source_url=source_url,
            max_lectures=max_lectures,
        )
        promotion_payload = {
            "decision": decision["decision"],
            "reason": decision["reason"],
            "course_match": decision.get("course_match", "unknown"),
            "action": decision.get("action", ""),
            "previous": _compact_readiness_snapshot(production_snapshot),
            "previous_course": _compact_readiness(decision.get("previous_course") or {}),
            "candidate": _compact_readiness(temp_readiness),
            "backup_path": "",
            "temp_store_root": str(temp_store_root),
            "promoted_course_id": temp_course_id if decision["promote"] else "",
        }
        if decision["promote"]:
            backup_path = _backup_sqlite_database(production_store.db_path)
            merge_result = production_store.merge_course_from_store(temp_store, temp_course_id)
            promotion_payload["backup_path"] = str(backup_path)
            promotion_payload["merge_result"] = merge_result
            production_store = SQLiteCourseStore(store_root)
            promoted_stage = str(decision.get("stage") or "promoted")
            production_store.append_import_event(
                run_id,
                stage=promoted_stage,
                status="completed" if temp_readiness.get("ready") else "partial",
                event_type="promotion_completed",
                message=decision["reason"],
                payload=promotion_payload,
            )
            run = production_store.update_import_run(
                run_id,
                course_id=temp_course_id,
                status="completed" if temp_readiness.get("ready") else "partial",
                stage=promoted_stage,
                total_lectures=int(temp_readiness.get("lecture_count") or 0),
                completed_lectures=int(temp_readiness.get("ready_lecture_count") or 0),
                failed_lectures=int(temp_readiness.get("missing_lecture_count") or 0),
            )
        else:
            production_store.update_import_run(
                run_id,
                status="failed",
                stage="promotion_blocked",
                total_lectures=int(temp_readiness.get("lecture_count") or 0),
                completed_lectures=int(temp_readiness.get("ready_lecture_count") or 0),
                failed_lectures=int(temp_readiness.get("missing_lecture_count") or 0),
            )
            production_store.append_import_event(
                run_id,
                stage="promotion_blocked",
                status="failed",
                event_type="promotion_blocked",
                message=decision["reason"],
                payload=promotion_payload,
            )
            run = production_store.read_import_run(run_id)
        return {
            "status": str(run.get("status") or ""),
            "run": run,
            "run_id": run_id,
            "readiness": temp_readiness,
            "promotion": promotion_payload,
        }
    except Exception as exc:  # noqa: BLE001
        message = _redact_secret(str(exc), bilibili_cookie)
        production_store.update_import_run(run_id, status="failed", stage="temp_import_failed")
        production_store.append_import_event(
            run_id,
            stage="temp_import_failed",
            status="failed",
            event_type="temp_import_failed",
            message=message,
            payload={"error_type": type(exc).__name__, "cookie_present": bool(str(bilibili_cookie or "").strip())},
        )
        raise RuntimeError(message) from exc
    finally:
        _forget_temp_import_store(run_id)


def _start_bilibili_qr_login() -> dict[str, Any]:
    _cleanup_expired_bilibili_qr_sessions()
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    request = Request(BILIBILI_QR_GENERATE_URL, headers=BILIBILI_QR_HEADERS)
    with opener.open(request, timeout=20) as response:  # noqa: S310 - public Bilibili API boundary.
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else {}
    if payload.get("code") != 0 or not isinstance(data, dict):
        raise RuntimeError(f"Bilibili QR generate failed: code={payload.get('code') if isinstance(payload, dict) else 'unknown'}")
    qr_url = str(data.get("url") or "").strip()
    qrcode_key = str(data.get("qrcode_key") or "").strip()
    if not qr_url or not qrcode_key:
        raise RuntimeError("Bilibili QR generate did not return a usable login URL")
    now = datetime.now(timezone.utc)
    session = BilibiliQrLoginSession(
        login_id=f"bili_qr_{uuid4().hex[:12]}",
        qrcode_key=qrcode_key,
        qr_url=qr_url,
        created_at=now,
        expires_at=now + timedelta(seconds=BILIBILI_QR_SESSION_TTL_SECONDS),
        cookie_jar=cookie_jar,
    )
    with _BILIBILI_QR_LOCK:
        _BILIBILI_QR_SESSIONS[session.login_id] = session
    return _bilibili_qr_public_payload(session, include_qr=True)


def _poll_bilibili_qr_login(login_id: str) -> dict[str, Any]:
    _cleanup_expired_bilibili_qr_sessions()
    session = _read_bilibili_qr_session(login_id)
    now = datetime.now(timezone.utc)
    if now >= session.expires_at:
        session.status = "expired"
        session.message = "二维码已过期"
        _forget_bilibili_qr_session(session.login_id)
        return _bilibili_qr_public_payload(session)
    opener = build_opener(HTTPCookieProcessor(session.cookie_jar))
    request_url = f"{BILIBILI_QR_POLL_URL}?{urlencode({'qrcode_key': session.qrcode_key})}"
    request = Request(request_url, headers=BILIBILI_QR_HEADERS)
    try:
        with opener.open(request, timeout=20) as response:  # noqa: S310 - public Bilibili API boundary.
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_redact_bilibili_qr_secret(str(exc), session.qrcode_key)) from exc
    data = payload.get("data") if isinstance(payload, dict) else {}
    if payload.get("code") != 0 or not isinstance(data, dict):
        raise RuntimeError(f"Bilibili QR poll failed: code={payload.get('code') if isinstance(payload, dict) else 'unknown'}")
    data_code = int(data.get("code") or 0)
    message = str(data.get("message") or "").strip()
    if data_code == 0:
        cookie_header = _cookie_header_from_jar(session.cookie_jar)
        if not cookie_header:
            raise RuntimeError("Bilibili QR login succeeded but no cookie was issued")
        session.cookie_header = cookie_header
        session.status = "succeeded"
        session.message = "扫码登录完成，可用于本次导入"
    elif data_code == 86090:
        session.status = "scanned"
        session.message = message or "已扫码，请在手机上确认"
    elif data_code == 86101:
        session.status = "pending"
        session.message = message or "等待扫码"
    elif data_code == 86038:
        session.status = "expired"
        session.message = message or "二维码已过期"
    else:
        session.status = "failed"
        session.message = message or f"Bilibili QR status {data_code}"
    if session.status in {"expired", "failed"}:
        _forget_bilibili_qr_session(session.login_id)
    return _bilibili_qr_public_payload(session)


def _clear_bilibili_qr_login(login_id: str) -> dict[str, Any]:
    _forget_bilibili_qr_session(login_id)
    return {
        "status": "completed",
        "login_id": "",
        "login_status": "cleared",
        "message": "扫码登录状态已清空。",
        "cookie_present": False,
    }


def _load_persisted_bilibili_cookie() -> str:
    with _BILIBILI_AUTH_LOCK:
        if not BILIBILI_AUTH_FILE.exists():
            return ""
        try:
            payload = json.loads(BILIBILI_AUTH_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
    pairs = _cookie_pairs_from_auth_payload(payload)
    return _cookie_header_from_pairs(pairs)


def _save_persisted_bilibili_cookie(cookie_header: str) -> dict[str, Any]:
    pairs = _parse_cookie_header_to_pairs(cookie_header)
    if not pairs:
        raise ValueError("Bilibili Cookie did not contain usable name=value pairs")
    payload = {
        "provider": "bilibili",
        "cookie_pairs": pairs,
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with _BILIBILI_AUTH_LOCK:
        BILIBILI_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path = BILIBILI_AUTH_FILE.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, BILIBILI_AUTH_FILE)
    return _bilibili_cookie_status()


def _clear_persisted_bilibili_cookie() -> None:
    with _BILIBILI_AUTH_LOCK:
        try:
            BILIBILI_AUTH_FILE.unlink()
        except FileNotFoundError:
            return


def _bilibili_cookie_status() -> dict[str, Any]:
    with _BILIBILI_AUTH_LOCK:
        if not BILIBILI_AUTH_FILE.exists():
            return {"stored": False, "cookie_names": [], "updated_at": ""}
        try:
            payload = json.loads(BILIBILI_AUTH_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"stored": False, "cookie_names": [], "updated_at": "", "warning": "stored auth file is unreadable"}
    pairs = _cookie_pairs_from_auth_payload(payload)
    return {
        "stored": bool(pairs),
        "cookie_names": sorted(pairs.keys()),
        "updated_at": str(payload.get("updated_at") or ""),
    }


def _cookie_pairs_from_auth_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    cookie_pairs = payload.get("cookie_pairs") or payload.get("cookies") or {}
    if not isinstance(cookie_pairs, dict):
        return {}
    return {
        str(key).strip(): str(value).strip()
        for key, value in cookie_pairs.items()
        if str(key).strip() and str(value).strip()
    }


def _parse_cookie_header_to_pairs(cookie_header: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in str(cookie_header or "").split(";"):
        if "=" not in part:
            continue
        raw_key, raw_value = part.split("=", 1)
        key = raw_key.strip()
        value = raw_value.strip()
        if key and value:
            pairs[key] = value
    return pairs


def _cookie_header_from_pairs(cookie_pairs: dict[str, str]) -> str:
    return "; ".join(
        f"{key}={value}"
        for key, value in cookie_pairs.items()
        if str(key).strip() and str(value).strip()
    )


def _consume_bilibili_qr_cookie(login_id: str) -> str:
    session = _read_bilibili_qr_session(login_id)
    if datetime.now(timezone.utc) >= session.expires_at:
        _forget_bilibili_qr_session(session.login_id)
        raise ValueError("Bilibili QR login expired; scan again before importing")
    if session.status != "succeeded" or not session.cookie_header:
        raise ValueError("Bilibili QR login is not ready for import")
    cookie_header = session.cookie_header
    _forget_bilibili_qr_session(session.login_id)
    return cookie_header


def _read_bilibili_qr_session(login_id: str) -> BilibiliQrLoginSession:
    cleaned = str(login_id or "").strip()
    with _BILIBILI_QR_LOCK:
        session = _BILIBILI_QR_SESSIONS.get(cleaned)
    if session is None:
        raise ValueError("Bilibili QR login session was not found or has expired")
    return session


def _forget_bilibili_qr_session(login_id: str) -> None:
    with _BILIBILI_QR_LOCK:
        _BILIBILI_QR_SESSIONS.pop(str(login_id or "").strip(), None)


def _cleanup_expired_bilibili_qr_sessions() -> None:
    now = datetime.now(timezone.utc)
    with _BILIBILI_QR_LOCK:
        expired = [login_id for login_id, session in _BILIBILI_QR_SESSIONS.items() if now >= session.expires_at]
        for login_id in expired:
            _BILIBILI_QR_SESSIONS.pop(login_id, None)


def _bilibili_qr_public_payload(session: BilibiliQrLoginSession, *, include_qr: bool = False) -> dict[str, Any]:
    payload = {
        "status": "completed",
        "login_id": session.login_id if session.status not in {"expired", "failed"} else "",
        "login_status": session.status,
        "message": session.message,
        "expires_at": session.expires_at.isoformat().replace("+00:00", "Z"),
        "ttl_seconds": max(0, int((session.expires_at - datetime.now(timezone.utc)).total_seconds())),
        "cookie_present": bool(session.cookie_header),
    }
    if include_qr:
        payload["qr_svg"] = _qr_svg_data_url(session.qr_url)
    return payload


def _cookie_header_from_jar(cookie_jar: CookieJar) -> str:
    parts = []
    for cookie in cookie_jar:
        name = str(cookie.name or "").strip()
        value = str(cookie.value or "").strip()
        if name and value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def _redact_bilibili_qr_secret(message: str, qrcode_key: str = "") -> str:
    redacted = str(message or "")
    cleaned_key = str(qrcode_key or "").strip()
    if cleaned_key:
        redacted = redacted.replace(cleaned_key, "[REDACTED_BILIBILI_QR_KEY]")
    redacted = re.sub(r"(qrcode_key=)[^&\s]+", r"\1[REDACTED_BILIBILI_QR_KEY]", redacted)
    return redacted


def _qr_svg_data_url(value: str) -> str:
    import base64
    from io import BytesIO

    try:
        import qrcode
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("QR renderer dependency is unavailable; install project dependencies and retry") from exc

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _backup_sqlite_database(db_path: Path) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_stamp()
    backup_path = backup_dir / f"{db_path.stem}.{timestamp}.bak{db_path.suffix}"
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
    else:
        backup_path.write_bytes(b"")
    return backup_path


def _replace_sqlite_database(*, source_db: Path, target_db: Path) -> None:
    if not source_db.exists():
        raise FileNotFoundError(f"candidate SQLite database not found: {source_db}")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target_db.with_name(f"{target_db.name}.replace-{uuid4().hex[:8]}.tmp")
    shutil.copy2(source_db, tmp_target)
    os.replace(tmp_target, target_db)


def _promotion_decision(
    previous_snapshot: dict[str, Any],
    candidate_readiness: dict[str, Any],
    *,
    source_url: str = "",
    max_lectures: int | None = None,
) -> dict[str, Any]:
    candidate = _compact_readiness(candidate_readiness)
    previous_course = _matching_readiness(previous_snapshot, candidate, source_url=source_url)
    candidate_lecture_count = int(candidate.get("lecture_count") or 0)
    if candidate_lecture_count <= 0:
        return {"promote": False, "decision": "blocked", "reason": "未入库：候选导入没有课程课时。", "course_match": "invalid"}
    if int(candidate.get("transcript_ready_count") or 0) <= 0:
        return {"promote": False, "decision": "blocked", "reason": "未入库：候选导入没有任何字幕转写。", "course_match": "invalid"}
    if max_lectures is not None:
        return {
            "promote": False,
            "decision": "blocked_probe_subset",
            "reason": "未入库：本次是限制课时数的探针导入，不自动写入正式课程库。",
            "course_match": "probe_subset",
        }
    if not previous_course:
        return {
            "promote": True,
            "decision": "merged_new_course",
            "stage": "merged_new_course",
            "action": "merge_course",
            "reason": "新课程已通过就绪检查，并合并入本地课程库。",
            "course_match": "new_course",
        }
    keys = ("transcript_ready_count", "note_ready_count", "atom_ready_count", "gate_ready_count", "ready_lecture_count")
    regressions = [key for key in keys if int(candidate.get(key) or 0) < int(previous_course.get(key) or 0)]
    if regressions:
        return {
            "promote": False,
            "decision": "blocked",
            "reason": f"未覆盖当前课程：候选导入质量低于同一课程现有数据（{', '.join(regressions)}）。",
            "course_match": "same_course",
            "previous_course": previous_course,
        }
    return {
        "promote": True,
        "decision": "replaced_same_course",
        "stage": "replaced_same_course",
        "action": "replace_course",
        "reason": "同一课程重导入已通过非回退检查，并替换该课程本地数据。",
        "course_match": "same_course",
        "previous_course": previous_course,
    }


def _store_readiness_snapshot(store: SQLiteCourseStore) -> dict[str, Any]:
    courses = store.list_courses()
    readiness_items: list[dict[str, Any]] = []
    for course in courses:
        course_id = str(course.get("course_id") or "")
        if not course_id:
            continue
        try:
            readiness_items.append(store.summarize_import_readiness(course_id))
        except Exception:
            continue
    return {"course_count": len(courses), "courses": readiness_items}


def _best_readiness(snapshot: dict[str, Any]) -> dict[str, Any]:
    courses = [dict(item) for item in snapshot.get("courses") or [] if isinstance(item, dict)]
    if not courses:
        return _empty_readiness()
    return max(courses, key=lambda item: _readiness_score(item))


def _matching_readiness(snapshot: dict[str, Any], candidate: dict[str, Any], *, source_url: str = "") -> dict[str, Any]:
    candidate_course_id = str(candidate.get("course_id") or "").strip()
    candidate_source_url = str((candidate.get("course") or {}).get("source_url") or source_url or "").strip()
    for item in snapshot.get("courses") or []:
        if not isinstance(item, dict):
            continue
        if candidate_course_id and str(item.get("course_id") or "").strip() == candidate_course_id:
            return dict(item)
        item_source_url = str((item.get("course") or {}).get("source_url") or "").strip()
        if candidate_source_url and item_source_url and _normalize_source_url(item_source_url) == _normalize_source_url(candidate_source_url):
            return dict(item)
    return {}


def _normalize_source_url(source_url: str) -> str:
    parsed = urlparse(str(source_url or "").strip())
    path = parsed.path.rstrip("/")
    query_items = [
        (key, value)
        for key, value in parse_qs(parsed.query, keep_blank_values=True).items()
        if key in {"p", "oid", "sid", "season_id", "series_id", "type"}
    ]
    query = urlencode(sorted((key, item) for key, values in query_items for item in values))
    return f"{parsed.netloc.lower()}{path}?{query}" if query else f"{parsed.netloc.lower()}{path}"


def _readiness_score(readiness: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    return (
        int(readiness.get("transcript_ready_count") or 0),
        int(readiness.get("note_ready_count") or 0),
        int(readiness.get("atom_ready_count") or 0),
        int(readiness.get("gate_ready_count") or 0),
        int(readiness.get("ready_lecture_count") or 0),
        int(readiness.get("total_segment_count") or 0),
    )


def _compact_readiness_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_count": int(snapshot.get("course_count") or 0),
        "best": _compact_readiness(_best_readiness(snapshot)),
    }


def _compact_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_id": str(readiness.get("course_id") or ""),
        "lecture_count": int(readiness.get("lecture_count") or 0),
        "ready_lecture_count": int(readiness.get("ready_lecture_count") or 0),
        "missing_lecture_count": int(readiness.get("missing_lecture_count") or 0),
        "transcript_ready_count": int(readiness.get("transcript_ready_count") or 0),
        "note_ready_count": int(readiness.get("note_ready_count") or 0),
        "atom_ready_count": int(readiness.get("atom_ready_count") or 0),
        "gate_ready_count": int(readiness.get("gate_ready_count") or 0),
        "total_segment_count": int(readiness.get("total_segment_count") or 0),
        "total_atom_count": int(readiness.get("total_atom_count") or 0),
        "total_gate_count": int(readiness.get("total_gate_count") or 0),
        "readiness_ratio": float(readiness.get("readiness_ratio") or 0.0),
    }


def _empty_readiness() -> dict[str, Any]:
    return {
        "course_id": "",
        "lecture_count": 0,
        "ready_lecture_count": 0,
        "missing_lecture_count": 0,
        "transcript_ready_count": 0,
        "note_ready_count": 0,
        "atom_ready_count": 0,
        "gate_ready_count": 0,
        "total_segment_count": 0,
        "total_atom_count": 0,
        "total_gate_count": 0,
        "readiness_ratio": 0.0,
    }


def _readiness_for_import_status(
    store: SQLiteCourseStore,
    run: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    course_id = str(run.get("course_id") or "")
    if course_id:
        try:
            return store.summarize_import_readiness(course_id)
        except Exception:
            pass
    promotion = _latest_promotion_payload(events)
    candidate = promotion.get("candidate") if isinstance(promotion, dict) else {}
    return candidate if isinstance(candidate, dict) else {}


def _latest_promotion_payload(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        if str(event.get("event_type") or "") in {"promotion_completed", "promotion_blocked"}:
            payload = event.get("payload")
            return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _latest_temp_import_payload(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        if str(event.get("event_type") or "") == "temp_import_started":
            payload = event.get("payload")
            if not isinstance(payload, dict):
                return {}
            return {
                "decision": "running",
                "reason": "正在临时库导入，当前数据尚未覆盖。",
                "previous": payload.get("previous") if isinstance(payload.get("previous"), dict) else {},
                "candidate": {},
                "backup_path": "",
                "promoted_course_id": "",
            }
    return {}


def _redact_secret(message: str, bilibili_cookie: str = "") -> str:
    return redact_bilibili_cookie(message, bilibili_cookie)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _chat_thread_for_stream(
    store: SQLiteCourseStore,
    *,
    course_id: str,
    message: str,
    thread_id: str,
    channel: str,
) -> dict[str, Any]:
    cleaned_thread_id = str(thread_id or "").strip()
    if cleaned_thread_id:
        try:
            thread = store.read_chat_thread(cleaned_thread_id)
        except ValueError:
            thread = {}
        if not thread:
            return store.create_chat_thread(
                course_id,
                title=_chat_thread_title(message),
                channel=channel,
            )
        if str(thread.get("course_id") or "") != course_id:
            raise ValueError(f"chat thread does not belong to course: {cleaned_thread_id}")
        return thread
    return store.create_chat_thread(
        course_id,
        title=_chat_thread_title(message),
        channel=channel,
    )


def _persist_hermes_stream_events(
    store: SQLiteCourseStore,
    *,
    thread: dict[str, Any],
    user_message: str,
    events: Any,
) -> Any:
    thread_id = str(thread.get("thread_id") or "")
    turn_key = uuid4().hex[:12]
    user_record = store.append_chat_message(
        thread_id,
        "user",
        user_message,
        message_id=f"{thread_id}::hermes_{turn_key}_001_user",
    )
    del user_record
    assistant_deltas: list[str] = []
    captured_events: list[dict[str, Any]] = []
    teaching_control_payload: dict[str, Any] = {}
    status = "completed"
    assistant_message_id = ""
    event_index = 0

    try:
        for raw_event in events:
            event = _sanitize_sse_event(raw_event)
            if event.get("event") == "thread_state":
                event = _local_thread_state_event(event, thread=thread, status=status)
            captured_events.append(event)
            if event.get("event") == "teaching_state":
                teaching_control_payload = _teaching_control_payload_from_state_event(event)
            if event.get("event") == "message_delta":
                assistant_deltas.append(str(((event.get("data") or {}).get("payload") or {}).get("delta") or ""))
            if event.get("event") == "done":
                done_payload = ((event.get("data") or {}).get("payload") or {})
                status = str(done_payload.get("status") or status)
            yield event
    finally:
        assistant_text = "".join(assistant_deltas).strip()
        if assistant_text:
            assistant = store.append_chat_message(
                thread_id,
                "assistant",
                assistant_text,
                message_id=f"{thread_id}::hermes_{turn_key}_002_assistant",
            )
            assistant_message_id = str(assistant.get("message_id") or "")
        for event in captured_events:
            event_index += 1
            store.append_chat_event(
                thread_id,
                _chat_event_type(event),
                _chat_event_payload(event),
                message_id=assistant_message_id,
                tool_name=_chat_event_tool_name(event),
                event_id=f"{thread_id}::hermes_{turn_key}_evt_{event_index:03d}",
            )
        if teaching_control_payload:
            event_index += 1
            store.append_chat_event(
                thread_id,
                "teaching_control",
                teaching_control_payload,
                message_id=assistant_message_id,
                tool_name="hermes_teaching_convergence",
                event_id=f"{thread_id}::hermes_{turn_key}_evt_{event_index:03d}",
            )
        if not captured_events:
            store.append_chat_event(
                thread_id,
                "error",
                {"reason": "empty_hermes_stream", "message": "Hermes stream ended without events."},
                event_id=f"{thread_id}::hermes_{turn_key}_evt_001",
            )
        elif status != "completed" and not assistant_message_id:
            store.append_chat_event(
                thread_id,
                "error",
                {"reason": status or "blocked", "message": "Hermes stream did not produce a persisted assistant message."},
                event_id=f"{thread_id}::hermes_{turn_key}_evt_{event_index + 1:03d}",
            )


def _chat_history_payload(store: SQLiteCourseStore, *, course_id: str, thread_id: str = "") -> dict[str, Any]:
    threads = store.list_chat_threads(course_id=course_id, channel="web")
    for thread in threads:
        thread["message_count"] = len(store.list_chat_messages(str(thread.get("thread_id") or "")))
    selected_thread = {}
    if thread_id:
        selected_thread = store.read_chat_thread(thread_id)
        if str(selected_thread.get("course_id") or "") != course_id:
            raise ValueError(f"chat thread does not belong to course: {thread_id}")
    elif threads:
        selected_thread = dict(threads[0])
    messages = store.list_chat_messages(str(selected_thread.get("thread_id") or "")) if selected_thread else []
    messages.sort(key=_chat_message_order_key)
    events = store.list_chat_events(str(selected_thread.get("thread_id") or "")) if selected_thread else []
    return {
        "status": "completed",
        "thread": selected_thread,
        "threads": threads,
        "messages": messages,
        "events": events,
    }


def _local_thread_state_event(event: dict[str, Any], *, thread: dict[str, Any], status: str) -> dict[str, Any]:
    data = dict(event.get("data") or {})
    data["thread"] = {
        "channel": str(thread.get("channel") or "web"),
        "local_history_available": True,
    }
    data["status"] = str(data.get("status") or status or "completed")
    data["route"] = str(data.get("route") or "hermes_frontdesk")
    return {
        "event": "thread_state",
        "id": "",
        "data": _sanitize_chat_event_payload(data),
    }


def _chat_message_order_key(message: dict[str, Any]) -> tuple[str, int, str]:
    role_rank = {"user": 0, "assistant": 1}.get(str(message.get("role") or ""), 2)
    return (str(message.get("created_at") or ""), role_rank, str(message.get("message_id") or ""))


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


def _is_visual_request(message: str) -> bool:
    lowered = str(message or "").lower()
    visual_terms = ("关键截图", "截图", "图示", "图片", "图像", "画面", "key screenshot")
    return any(term in lowered for term in visual_terms)


def _build_visual_sse_events(
    *,
    store: SQLiteCourseStore,
    course_id: str,
    lecture_id: str,
    message: str,
) -> list[dict[str, Any]]:
    base_payload = {"course_id": course_id, "lecture_id": lecture_id, "query": message}
    events = [
        {
            "event": "tool_chain",
            "id": "",
            "data": {"payload": {"tool": "course_visual_evidence_send", "status": "running", **base_payload}},
        }
    ]
    visuals = store.list_visual_evidence(course_id=course_id, lecture_id=lecture_id)
    generated = [item for item in visuals if "generated_keyframe" in str(item.get("provenance") or "")]
    visual = dict((generated or [{}])[0])
    if not visual:
        message_text = "当前课时还没有可发送的真实关键截图。导入记录没有生成视频关键帧时，不能用示意图代替课程截图。"
        events.extend(
            [
                {
                    "event": "error",
                    "id": "",
                    "data": {"payload": {"reason": "no_visual_evidence", "message": message_text}},
                },
                {"event": "done", "id": "", "data": {"payload": {"status": "blocked"}}},
            ]
        )
        return events
    text = str(visual.get("explanation") or visual.get("title") or "这是当前课时的关键截图。")
    events.extend(
        [
            {
                "event": "media",
                "id": str(visual.get("visual_id") or ""),
                "data": {
                    "payload": {
                        "media_type": "image",
                        "source": "VISUAL_EVIDENCE",
                        "visual_id": str(visual.get("visual_id") or ""),
                        "image_path": str(visual.get("image_path") or ""),
                        "title": str(visual.get("title") or ""),
                        "explanation": str(visual.get("explanation") or ""),
                    }
                },
            },
            {"event": "message_delta", "id": "", "data": {"payload": {"delta": text}}},
            {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
        ]
    )
    return events


def _build_web_course_context(
    *,
    store: SQLiteCourseStore,
    course_id: str,
    course: dict[str, Any],
    lecture_id: str = "",
    lecture_sequence: str = "",
) -> dict[str, Any]:
    lectures = store.read_lectures(course_id)
    selected_lecture = _select_context_lecture(
        lectures,
        lecture_id=lecture_id,
        lecture_sequence=lecture_sequence,
    )
    reader: dict[str, Any] = {}
    if selected_lecture:
        reader = store.read_lecture_reader(
            course_id,
            lecture_id=str(selected_lecture.get("lecture_id") or ""),
        )
    selected_lecture_id = str((selected_lecture or {}).get("lecture_id") or "")
    cards = store.list_knowledge_cards(course_id=course_id, lecture_id=selected_lecture_id)
    if not cards:
        cards = store.list_knowledge_cards(course_id=course_id)
    return {
        "course": dict(course),
        "lectures": lectures,
        "lecture": dict(selected_lecture or {}),
        "reader": reader,
        "knowledge_cards": cards,
    }


def _select_context_lecture(
    lectures: list[dict[str, Any]],
    *,
    lecture_id: str = "",
    lecture_sequence: str = "",
) -> dict[str, Any]:
    if lecture_id:
        for lecture in lectures:
            if str(lecture.get("lecture_id") or "") == lecture_id:
                return dict(lecture)
    if lecture_sequence:
        for lecture in lectures:
            if str(lecture.get("sequence") or "") == str(lecture_sequence):
                return dict(lecture)
    return dict(lectures[0]) if lectures else {}


def _chat_thread_title(message: str) -> str:
    collapsed = " ".join(str(message or "").split())
    if len(collapsed) <= 48:
        return collapsed or "New chat"
    return f"{collapsed[:45].rstrip()}..."


def _sanitize_sse_event(event: dict[str, Any]) -> dict[str, Any]:
    raw = dict(event or {})
    return {
        "event": str(raw.get("event") or "message"),
        "id": str(raw.get("id") or ""),
        "data": _sanitize_chat_event_payload(raw.get("data") or {}),
    }


def _chat_event_type(event: dict[str, Any]) -> str:
    event_type = str(event.get("event") or "").strip()
    if event_type in {"message_delta", "media", "done", "error"}:
        return event_type
    if event_type in {"route_ready", "teaching_state", "tool_chain"}:
        return "tool_result"
    return "tool_result"


def _chat_event_tool_name(event: dict[str, Any]) -> str:
    event_type = str(event.get("event") or "").strip()
    if event_type == "tool_chain":
        return "hermes_tool_progress"
    if event_type in {"route_ready", "teaching_state"}:
        return f"hermes_{event_type}"
    return ""


def _chat_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    return {
        "sse_event": str(event.get("event") or ""),
        "sse_id": str(event.get("id") or ""),
        "payload": _sanitize_chat_event_payload(payload),
    }


def _teaching_control_payload_from_state_event(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    control = payload.get("teaching_control") if isinstance(payload.get("teaching_control"), dict) else {}
    gate = payload.get("learning_signals") if isinstance(payload.get("learning_signals"), dict) else {}
    atoms = payload.get("knowledge_atoms") if isinstance(payload.get("knowledge_atoms"), list) else []
    return _sanitize_chat_event_payload(
        {
            "contract": str(control.get("contract") or ""),
            "current_atom_index": int(control.get("position_index") or 0),
            "completed_atom_count": int(control.get("passed_count") or 0),
            "total_atom_count": int(control.get("total_count") or len(atoms)),
            "progress_ratio_label": str(payload.get("progress_ratio_label") or ""),
            "student_visible": {
                "next_step_label": str(payload.get("next_step_label") or control.get("next_step_label") or ""),
                "knowledge_atoms": atoms,
            },
            "mastery_signals": {
                "retrieval": bool(gate.get("retrieval_signal")),
                "evidence": bool(gate.get("grounded_evidence_signal")),
                "causal": bool(gate.get("causal_chain_signal")),
                "boundary": bool(gate.get("boundary_signal")),
                "transfer": bool(gate.get("transfer_signal")),
                "overquestioning_risk": bool(gate.get("overquestioning_risk")),
                "scope_challenge": bool(gate.get("scope_challenge_signal")),
                "probe_count": int(gate.get("same_atom_probe_count") or 0),
            },
        }
    )


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
    redacted = str(value or "")
    for token in value.split():
        cleaned = token.strip(".,;:!?()[]{}\"'")
        path = Path(cleaned.replace("\\", "/"))
        is_windows_absolute = len(cleaned) >= 3 and cleaned[1:3] in {":/", ":\\"}
        if is_windows_absolute or path.is_absolute() or ".." in path.parts:
            redacted = redacted.replace(cleaned, "[redacted-path]")
    return redacted


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


def _optional_positive_int_body(raw_value: Any) -> int | None:
    if raw_value in (None, ""):
        return None
    parsed = int(raw_value)
    if parsed <= 0:
        raise ValueError(f"positive integer expected: {raw_value}")
    return parsed


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
    parser.add_argument("--public-demo", action="store_true", help="Run a read-only public demo surface.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handler = Course2KnowledgeWebHandler
    handler.store_root = Path(args.store_root).expanduser().resolve()
    handler.public_demo = bool(args.public_demo or _bool_env(PUBLIC_DEMO_ENV))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        json.dumps(
            {
                "status": "serving",
                "url": f"http://{args.host}:{args.port}",
                "store_root": str(handler.store_root),
                "public_demo": handler.public_demo,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
