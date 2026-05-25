from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.cookiejar import Cookie


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER = ROOT / "apps" / "web" / "server.py"
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_store import (  # noqa: E402
    KnowledgeCardRecord,
    SQLiteCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_course_skeleton,
)


def load_web_server_module():
    spec = importlib.util.spec_from_file_location("course2knowledge_lite_web_server", WEB_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Web Lite server module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_web_hermes_adapter_module():
    import course2knowledge_lite_store.web_hermes.adapter as adapter

    return adapter


class WebLiteTests(unittest.TestCase):
    def test_bilibili_cookie_can_be_persisted_used_and_cleared_without_api_leakage(self) -> None:
        web_server = load_web_server_module()

        previous_auth_file = web_server.BILIBILI_AUTH_FILE
        previous_worker = web_server._start_import_worker
        captured_workers: list[dict[str, object]] = []
        web_server._start_import_worker = lambda **kwargs: captured_workers.append(kwargs)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                auth_file = Path(temp_dir) / ".codex" / "auth" / "bilibili.json"
                web_server.BILIBILI_AUTH_FILE = auth_file
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir) / "store"
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    saved = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/bilibili/cookie/save",
                        {"bilibili_cookie": "SESSDATA=secret-session; bili_jct=secret-csrf; DedeUserID=42"},
                        expected_status=201,
                    )
                    status = _request_json(host, port, "GET", "/api/bilibili/cookie")
                    imported = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {"source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season"},
                        expected_status=201,
                    )
                    store = web_server.SQLiteCourseStore(web_server.Course2KnowledgeWebHandler.store_root)
                    events = store.list_import_events(str(imported["run_id"]))
                    cleared = _request_json(host, port, "POST", "/api/bilibili/cookie/clear", {})
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.BILIBILI_AUTH_FILE = previous_auth_file
            web_server._start_import_worker = previous_worker

        serialized = json.dumps(
            {"saved": saved, "status": status, "imported": imported, "events": events, "cleared": cleared},
            ensure_ascii=False,
        )
        self.assertTrue(saved["auth"]["stored"])
        self.assertEqual(status["auth"]["cookie_names"], ["DedeUserID", "SESSDATA", "bili_jct"])
        self.assertEqual(captured_workers[0]["bilibili_cookie"], "DedeUserID=42; SESSDATA=secret-session; bili_jct=secret-csrf")
        self.assertEqual(events[0]["payload"]["auth_source"], "stored_cookie")
        self.assertTrue(events[0]["payload"]["stored_cookie_available"])
        self.assertFalse(cleared["auth"]["stored"])
        self.assertFalse(auth_file.exists())
        self.assertNotIn("secret-session", serialized)
        self.assertNotIn("secret-csrf", serialized)
        self.assertNotIn("SESSDATA=", serialized)

    def test_bilibili_import_remember_persists_manual_cookie_without_event_leakage(self) -> None:
        web_server = load_web_server_module()

        previous_auth_file = web_server.BILIBILI_AUTH_FILE
        previous_worker = web_server._start_import_worker
        captured_workers: list[dict[str, object]] = []
        web_server._start_import_worker = lambda **kwargs: captured_workers.append(kwargs)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                auth_file = Path(temp_dir) / ".codex" / "auth" / "bilibili.json"
                web_server.BILIBILI_AUTH_FILE = auth_file
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir) / "store"
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    imported = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {
                            "source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                            "bilibili_cookie": "SESSDATA=remember-secret; bili_jct=remember-csrf",
                            "remember_bilibili_cookie": True,
                            "max_lectures": 1,
                        },
                        expected_status=201,
                    )
                    status = _request_json(host, port, "GET", "/api/bilibili/cookie")
                    store = web_server.SQLiteCourseStore(web_server.Course2KnowledgeWebHandler.store_root)
                    events = store.list_import_events(str(imported["run_id"]))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.BILIBILI_AUTH_FILE = previous_auth_file
            web_server._start_import_worker = previous_worker

        serialized = json.dumps({"imported": imported, "status": status, "events": events}, ensure_ascii=False)
        self.assertTrue(status["auth"]["stored"])
        self.assertEqual(status["auth"]["cookie_names"], ["SESSDATA", "bili_jct"])
        self.assertEqual(captured_workers[0]["bilibili_cookie"], "SESSDATA=remember-secret; bili_jct=remember-csrf")
        self.assertEqual(captured_workers[0]["max_lectures"], 1)
        self.assertEqual(events[0]["payload"]["auth_source"], "manual_cookie")
        self.assertTrue(events[0]["payload"]["remember_cookie"])
        self.assertNotIn("remember-secret", serialized)
        self.assertNotIn("remember-csrf", serialized)
        self.assertNotIn("SESSDATA=", serialized)

    def test_bilibili_qr_login_api_keeps_secrets_backend_only(self) -> None:
        web_server = load_web_server_module()

        previous_build_opener = web_server.build_opener
        previous_qr = web_server._qr_svg_data_url
        previous_worker = web_server._start_import_worker
        captured_workers: list[dict[str, object]] = []
        calls: list[str] = []
        web_server.build_opener = lambda processor: _FakeBilibiliQrOpener(processor.cookiejar, calls)
        web_server._qr_svg_data_url = lambda _value: "data:image/png;base64,ZmFrZQ=="
        web_server._start_import_worker = lambda **kwargs: captured_workers.append(kwargs)
        web_server._BILIBILI_QR_SESSIONS.clear()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    qr = _request_json(host, port, "POST", "/api/bilibili/login/qrcode", {}, expected_status=201)
                    status = _request_json(
                        host,
                        port,
                        "GET",
                        f"/api/bilibili/login/qrcode/status?login_id={qr['login_id']}",
                    )
                    imported = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {
                            "source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                            "bilibili_qr_login_id": qr["login_id"],
                        },
                        expected_status=201,
                    )
                    store = web_server.SQLiteCourseStore(Path(temp_dir))
                    events = store.list_import_events(str(imported["run_id"]))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.build_opener = previous_build_opener
            web_server._qr_svg_data_url = previous_qr
            web_server._start_import_worker = previous_worker
            web_server._BILIBILI_QR_SESSIONS.clear()

        serialized = json.dumps({"qr": qr, "status": status, "imported": imported, "events": events}, ensure_ascii=False)
        self.assertEqual(qr["login_status"], "pending")
        self.assertEqual(status["login_status"], "succeeded")
        self.assertTrue(status["cookie_present"])
        self.assertEqual(captured_workers[0]["bilibili_cookie"], "SESSDATA=secret-session; bili_jct=secret-csrf")
        self.assertIn("qrcode/generate", calls[0])
        self.assertIn("qrcode/poll", calls[1])
        self.assertIn("auth_source", events[0]["payload"])
        self.assertEqual(events[0]["payload"]["auth_source"], "qr_login")
        self.assertNotIn("secret-session", serialized)
        self.assertNotIn("secret-csrf", serialized)
        self.assertNotIn("fake-qrcode-key", serialized)
        self.assertNotIn("qrcode_key", serialized)

    def test_bilibili_qr_login_must_succeed_before_import(self) -> None:
        web_server = load_web_server_module()
        web_server._BILIBILI_QR_SESSIONS.clear()
        session = web_server.BilibiliQrLoginSession(
            login_id="bili_qr_pending_test",
            qrcode_key="fake-qrcode-key",
            qr_url="https://account.bilibili.com/h5/account-h5/auth/qr",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        web_server._BILIBILI_QR_SESSIONS[session.login_id] = session
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    payload = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {
                            "source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                            "bilibili_qr_login_id": session.login_id,
                        },
                        expected_status=400,
                    )
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server._BILIBILI_QR_SESSIONS.clear()

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("not ready", payload["error"])
        self.assertNotIn("fake-qrcode-key", serialized)

    def test_web_import_api_writes_pipeline_run_and_returns_receipt(self) -> None:
        web_server = load_web_server_module()

        def fake_import(source_url: str, *, store_root: str | Path, **_: object) -> dict[str, object]:
            skeleton = build_course_skeleton(
                title="AI interview collection",
                source_url=source_url,
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BV00000001",
                        "title": "RAG and Agent",
                        "source_url": "https://www.bilibili.com/video/BV00000001",
                    },
                    {
                        "sequence": 2,
                        "bvid": "BV00000002",
                        "title": "Embedding and retrieval",
                        "source_url": "https://www.bilibili.com/video/BV00000002",
                    },
                ],
                now="2026-05-15T00:00:00Z",
            )
            store = SQLiteCourseStore(store_root)
            paths = store.write_skeleton(skeleton)
            run_id = str(_.get("run_id") or "")
            run = store.update_import_run(
                run_id,
                course_id=skeleton.course.course_id,
                status="partial",
                stage="ready_gate_blocked",
                total_lectures=2,
                completed_lectures=0,
                failed_lectures=2,
                now="2026-05-15T00:01:00Z",
            )
            store.append_import_event(
                run["run_id"],
                stage="ready_gate_blocked",
                status="partial",
                event_type="ready_gate",
                message="not ready",
                payload={"ready": False},
                now="2026-05-15T00:02:00Z",
            )
            return {
                "status": "partial",
                "run_id": run["run_id"],
                "run": run,
                "course": skeleton.course.to_dict(),
                "lectures": [lecture.to_dict() for lecture in skeleton.lectures],
                "import_status": skeleton.import_status.to_dict(),
                "readiness": store.summarize_import_readiness(skeleton.course.course_id),
                "paths": paths,
            }

        previous_import = web_server.import_collection_pipeline_to_store
        previous_worker = web_server._start_import_worker
        web_server.import_collection_pipeline_to_store = fake_import
        web_server._start_import_worker = lambda **kwargs: fake_import(
            kwargs["source_url"],
            store_root=kwargs["store_root"],
            run_id=kwargs["run_id"],
        )
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    payload = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {
                            "source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                        },
                        expected_status=201,
                    )
                    courses = _request_json(host, port, "GET", "/api/courses")
                    import_status = _request_json(
                        host,
                        port,
                        "GET",
                        f"/api/import/status?run_id={payload['run_id']}",
                    )
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.import_collection_pipeline_to_store = previous_import
            web_server._start_import_worker = previous_worker

        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["run_id"].startswith("lite_import_"))
        self.assertEqual(payload["run"]["stage"], "queued")
        self.assertEqual(payload["lecture_count"], 0)
        self.assertEqual(import_status["run"]["stage"], "ready_gate_blocked")
        self.assertFalse(import_status["readiness"]["ready"])
        self.assertEqual(import_status["events"][0]["event_type"], "import_requested")
        self.assertIn("ready_gate", [event["event_type"] for event in import_status["events"]])
        self.assertEqual(len(courses["courses"]), 1)
        self.assertEqual(courses["courses"][0]["lecture_count"], 2)

    def test_public_demo_runtime_is_readonly_but_browsing_still_works(self) -> None:
        web_server = load_web_server_module()

        previous_public_demo = web_server.Course2KnowledgeWebHandler.public_demo
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                _store_with_transcript(temp_dir)
                web_server.Course2KnowledgeWebHandler.public_demo = True
                web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
                server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    runtime = _request_json(host, port, "GET", "/api/runtime")
                    courses = _request_json(host, port, "GET", "/api/courses")
                    blocked_import = _request_json(
                        host,
                        port,
                        "POST",
                        "/api/import",
                        {"source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season"},
                        expected_status=400,
                    )
                    blocked_delete = _request_json(
                        host,
                        port,
                        "DELETE",
                        f"/api/courses?course_id={courses['courses'][0]['course_id']}",
                        expected_status=400,
                    )
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.Course2KnowledgeWebHandler.public_demo = previous_public_demo

        self.assertTrue(runtime["runtime"]["public_demo"])
        self.assertFalse(runtime["runtime"]["mutable_course_store"])
        self.assertEqual(len(courses["courses"]), 1)
        self.assertEqual(blocked_import["status"], "failed")
        self.assertEqual(blocked_delete["status"], "failed")
        self.assertIn("public demo mode is read-only", blocked_import["error"])
        self.assertIn("public demo mode is read-only", blocked_delete["error"])

    def test_web_static_text_assets_include_utf8_charset(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                connection = HTTPConnection(host, port, timeout=10)
                connection.request("GET", "/static/app.js")
                response = connection.getresponse()
                content_type = response.getheader("Content-Type")
                response.read()
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 200)
        self.assertIn("charset=utf-8", str(content_type).lower())

    def test_web_import_status_exposes_temp_progress_without_temp_paths(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            run = store.create_import_run(
                course_id="",
                source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                source_platform="bilibili",
                status="running",
                stage="temp_import",
                total_lectures=0,
            )
            store.append_import_event(
                str(run["run_id"]),
                stage="temp_import",
                status="running",
                event_type="temp_import_started",
                message="Importing into a temporary SQLite store before any overwrite.",
                payload={"previous": {"course_count": 0, "best": {}}},
            )
            temp_root = Path(temp_dir) / "tmp" / "guarded-reimports" / f"{run['run_id']}_candidate"
            temp_root.mkdir(parents=True)
            temp_store = SQLiteCourseStore(temp_root)
            temp_run = temp_store.create_import_run(
                run_id=str(run["run_id"]),
                course_id="course_progress",
                source_url=str(run["source_url"]),
                source_platform="bilibili",
                status="running",
                stage="lecture_compile",
                total_lectures=3,
                completed_lectures=1,
                failed_lectures=0,
            )
            temp_store.append_import_event(
                str(temp_run["run_id"]),
                stage="lecture_compile",
                status="completed",
                event_type="lecture_completed",
                message="Lecture 1 transcript and note ready",
                payload={"lecture_id": "course_progress::lecture::001", "segment_count": 8},
            )
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                status = _request_json(host, port, "GET", f"/api/import/status?run_id={run['run_id']}")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        serialized = json.dumps(status, ensure_ascii=False)
        self.assertTrue(status["progress"]["available"])
        self.assertEqual(status["progress"]["run"]["stage"], "lecture_compile")
        self.assertEqual(status["progress"]["run"]["completed_lectures"], 1)
        self.assertEqual(status["progress"]["events"][0]["event_type"], "lecture_completed")
        self.assertNotIn(str(temp_root), serialized)
        self.assertNotIn("temp_store_root", serialized)

    def test_web_import_cancel_also_cancels_temp_store_run(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            run = store.create_import_run(
                course_id="",
                source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                source_platform="bilibili",
                status="running",
                stage="temp_import",
            )
            temp_root = Path(temp_dir) / "tmp" / "guarded-reimports" / f"{run['run_id']}_candidate"
            temp_root.mkdir(parents=True)
            temp_store = SQLiteCourseStore(temp_root)
            temp_store.create_import_run(
                run_id=str(run["run_id"]),
                course_id="course_progress",
                source_url=str(run["source_url"]),
                source_platform="bilibili",
                status="running",
                stage="lecture_compile",
                total_lectures=3,
                completed_lectures=1,
            )
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                cancelled = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/import/cancel",
                    {"run_id": run["run_id"]},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            temp_run = SQLiteCourseStore(temp_root).read_import_run(str(run["run_id"]))

        self.assertEqual(cancelled["run"]["status"], "cancelled")
        self.assertEqual(temp_run["status"], "cancelled")

    def test_web_api_helpers_read_reader_search_and_qa_from_transcripts(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)

            courses = web_server._list_courses(Path(temp_dir))
            reader = store.read_lecture_reader(course_id, lecture_sequence=1)
            hits = store.search_transcripts(course_id, "RAG Agent")
            answer = web_server.answer_course_question(
                store=store,
                course_id=course_id,
                question="RAG 和 Agent 的区别是什么？",
            )

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["lecture_count"], 1)
        self.assertEqual(courses[0]["lecture_transcript_count"], 1)
        self.assertTrue(reader["has_transcript"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(answer["status"], "answered")
        self.assertEqual(answer["citation_count"], 1)

    def test_web_import_cancel_and_retry_failed_use_import_run_ledger(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            run = store.create_import_run(
                course_id=course_id,
                source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                status="partial",
                stage="ready_gate_blocked",
                total_lectures=1,
                completed_lectures=0,
                failed_lectures=1,
                now="2026-05-19T00:00:00Z",
            )
            started = []
            previous_worker = web_server._start_import_worker
            web_server._start_import_worker = lambda **kwargs: started.append(kwargs)
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                cancelled = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/import/cancel",
                    {"run_id": run["run_id"]},
                )
                retry = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/import/retry-failed",
                    {"run_id": run["run_id"]},
                    expected_status=202,
                )
            finally:
                web_server._start_import_worker = previous_worker
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(cancelled["run"]["status"], "cancelled")
        self.assertEqual(retry["status"], "accepted")
        self.assertEqual(retry["run"]["stage"], "retry_failed_lessons")
        self.assertEqual(started[0]["run_id"], retry["run_id"])
        self.assertEqual(started[0]["source_url"], "https://space.bilibili.com/1112988584/lists/7726472?type=season")

    def test_web_import_status_backfills_legacy_course_run_ledger(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            self.assertEqual(store.list_import_runs(course_id=course_id), [])
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                status = _request_json(host, port, "GET", f"/api/import/status?course_id={course_id}")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            runs = store.list_import_runs(course_id=course_id)

        self.assertEqual(len(status["runs"]), 1)
        self.assertEqual(status["runs"][0]["run_id"], runs[0]["run_id"])
        self.assertEqual(status["runs"][0]["stage"], "ready_gate_blocked")
        self.assertFalse(status["readiness"]["ready"])
        self.assertIn("lesson_note", status["readiness"]["lectures"][0]["missing"])
        self.assertEqual(status["readiness"]["latest_run"]["run_id"], runs[0]["run_id"])

    def test_guarded_reimport_blocks_lower_quality_candidate_without_overwrite(self) -> None:
        web_server = load_web_server_module()

        def fake_empty_import(source_url: str, *, store_root: str | Path, **_: object) -> dict[str, object]:
            skeleton = build_course_skeleton(
                title="empty candidate",
                source_url=source_url,
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BV00000099",
                        "title": "Empty",
                        "source_url": "https://www.bilibili.com/video/BV00000099",
                    }
                ],
                now="2026-05-19T00:00:00Z",
            )
            store = SQLiteCourseStore(store_root)
            store.write_skeleton(skeleton)
            return {
                "status": "failed",
                "course": skeleton.course.to_dict(),
                "readiness": store.summarize_import_readiness(skeleton.course.course_id),
            }

        previous_import = web_server.import_collection_pipeline_to_store
        web_server.import_collection_pipeline_to_store = fake_empty_import
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                store, course_id = _store_with_transcript(temp_dir)
                old_db_bytes = Path(store.db_path).read_bytes()
                run = store.create_import_run(
                    course_id="",
                    source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                    status="queued",
                    stage="queued",
                )

                result = web_server._run_guarded_reimport(
                    run_id=str(run["run_id"]),
                    source_url=str(run["source_url"]),
                    store_root=Path(temp_dir),
                    fetch_transcripts=True,
                    bilibili_cookie="SESSDATA=should-not-leak",
                )
                persisted_store = SQLiteCourseStore(temp_dir)
                status = persisted_store.read_import_run(str(run["run_id"]))
                events = persisted_store.list_import_events(str(run["run_id"]))
                courses = persisted_store.list_courses()
                remaining_lectures = persisted_store.read_lectures(course_id)
                remaining_segments = persisted_store.read_transcript_segments(course_id, remaining_lectures[0]["lecture_id"])
                db_changed_for_ledger = Path(persisted_store.db_path).read_bytes() != old_db_bytes
        finally:
            web_server.import_collection_pipeline_to_store = previous_import

        self.assertEqual(result["promotion"]["decision"], "blocked")
        self.assertEqual(status["stage"], "promotion_blocked")
        self.assertEqual([course["course_id"] for course in courses], [course_id])
        self.assertTrue(db_changed_for_ledger)
        self.assertEqual(len(remaining_segments), 1)
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("should-not-leak", serialized)

    def test_guarded_reimport_merges_new_course_even_when_existing_global_best_is_larger(self) -> None:
        web_server = load_web_server_module()

        def fake_ready_import(source_url: str, *, store_root: str | Path, **_: object) -> dict[str, object]:
            skeleton = build_course_skeleton(
                title="New smaller ready course",
                source_url=source_url,
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BVNEW00001",
                        "title": "New ready lecture",
                        "source_url": "https://www.bilibili.com/video/BVNEW00001",
                    }
                ],
                course_id="course_new_ready",
                now="2026-05-20T00:01:00Z",
            )
            store = SQLiteCourseStore(store_root)
            store.write_skeleton(skeleton)
            lecture = skeleton.lectures[0]
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture.lecture_id}::seg::1",
                        lecture_id=lecture.lecture_id,
                        start_seconds=0,
                        end_seconds=8,
                        text="A new course can be smaller than the existing global best and still be complete.",
                    )
                ],
            )
            store.create_note(skeleton.course.course_id, lecture.lecture_id, "Generated note", now="2026-05-19T00:01:00Z")
            store.generate_knowledge_cards(
                skeleton.course.course_id,
                lecture_id=lecture.lecture_id,
                overwrite=True,
                compile_mode="fallback",
                compile_provider=None,
            )
            return {
                "status": "completed",
                "course": store.read_course(skeleton.course.course_id),
                "readiness": store.summarize_import_readiness(skeleton.course.course_id),
            }

        previous_import = web_server.import_collection_pipeline_to_store
        web_server.import_collection_pipeline_to_store = fake_ready_import
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                old_store = SQLiteCourseStore(temp_dir)
                existing = build_course_skeleton(
                    title="Existing larger course",
                    source_url="https://www.bilibili.com/video/BVEXISTING",
                    video_refs=[
                        {
                            "sequence": index,
                            "bvid": "BVEXISTING",
                            "title": f"Existing lecture {index}",
                            "source_url": f"https://www.bilibili.com/video/BVEXISTING?p={index}",
                        }
                        for index in range(1, 3)
                    ],
                    course_id="course_existing_large",
                    now="2026-05-20T00:00:00Z",
                )
                old_store.write_skeleton(existing)
                for lecture in existing.lectures:
                    old_store.write_transcript_segments(
                        existing.course.course_id,
                        lecture.lecture_id,
                        [
                            TranscriptSegmentRecord(
                                segment_id=f"{lecture.lecture_id}::seg::1",
                                lecture_id=lecture.lecture_id,
                                start_seconds=0,
                                end_seconds=6,
                                text="Existing course evidence",
                            )
                        ],
                    )
                    old_store.create_note(existing.course.course_id, lecture.lecture_id, "Existing note")
                    old_store.generate_knowledge_cards(
                        existing.course.course_id,
                        lecture_id=lecture.lecture_id,
                        overwrite=True,
                        compile_mode="fallback",
                        compile_provider=None,
                    )
                thread = old_store.create_chat_thread("course_existing_large", title="Keep thread", thread_id="thread_existing")
                old_store.append_chat_message(str(thread["thread_id"]), "user", "Keep this chat")
                run = old_store.create_import_run(
                    course_id="",
                    source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                    status="queued",
                    stage="queued",
                )

                result = web_server._run_guarded_reimport(
                    run_id=str(run["run_id"]),
                    source_url=str(run["source_url"]),
                    store_root=Path(temp_dir),
                    fetch_transcripts=True,
                    bilibili_cookie="SESSDATA=should-not-leak",
                )
                promoted_store = SQLiteCourseStore(temp_dir)
                status = promoted_store.read_import_run(str(run["run_id"]))
                events = promoted_store.list_import_events(str(run["run_id"]))
                promotion = next(event["payload"] for event in events if event["event_type"] == "promotion_completed")
                backup_path = Path(str(promotion["backup_path"]))
                backup_exists = backup_path.exists()
                courses = promoted_store.list_courses()
                kept_messages = promoted_store.list_chat_messages("thread_existing")
        finally:
            web_server.import_collection_pipeline_to_store = previous_import

        self.assertEqual(result["promotion"]["decision"], "merged_new_course")
        self.assertEqual(status["stage"], "merged_new_course")
        self.assertTrue(backup_exists)
        self.assertEqual({course["course_id"] for course in courses}, {"course_existing_large", "course_new_ready"})
        self.assertEqual(len(kept_messages), 1)
        self.assertEqual(promotion["course_match"], "new_course")
        self.assertNotIn("should-not-leak", json.dumps(events, ensure_ascii=False))

    def test_guarded_reimport_replaces_same_course_when_candidate_is_not_worse(self) -> None:
        web_server = load_web_server_module()

        def fake_same_course_import(source_url: str, *, store_root: str | Path, **_: object) -> dict[str, object]:
            store, course_id = _store_with_transcript(str(store_root))
            course = store.read_course(course_id)
            lecture = store.read_lectures(course_id)[0]
            store.create_note(course_id, lecture["lecture_id"], "Generated note", now="2026-05-19T00:01:00Z")
            store.generate_knowledge_cards(
                course_id,
                lecture_id=lecture["lecture_id"],
                overwrite=True,
                compile_mode="fallback",
                compile_provider=None,
            )
            return {
                "status": "completed",
                "course": course,
                "readiness": store.summarize_import_readiness(course_id),
            }

        previous_import = web_server.import_collection_pipeline_to_store
        web_server.import_collection_pipeline_to_store = fake_same_course_import
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                old_store, course_id = _store_with_transcript(temp_dir)
                lecture = old_store.read_lectures(course_id)[0]
                old_store.create_note(course_id, lecture["lecture_id"], "Old note", now="2026-05-19T00:00:00Z")
                old_store.generate_knowledge_cards(
                    course_id,
                    lecture_id=lecture["lecture_id"],
                    overwrite=True,
                    compile_mode="fallback",
                    compile_provider=None,
                )
                run = old_store.create_import_run(
                    course_id="",
                    source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                    status="queued",
                    stage="queued",
                )

                result = web_server._run_guarded_reimport(
                    run_id=str(run["run_id"]),
                    source_url=str(run["source_url"]),
                    store_root=Path(temp_dir),
                    fetch_transcripts=True,
                )
                promoted_store = SQLiteCourseStore(temp_dir)
                status = promoted_store.read_import_run(str(run["run_id"]))
                events = promoted_store.list_import_events(str(run["run_id"]))
                promotion = next(event["payload"] for event in events if event["event_type"] == "promotion_completed")
        finally:
            web_server.import_collection_pipeline_to_store = previous_import

        self.assertEqual(result["promotion"]["decision"], "replaced_same_course")
        self.assertEqual(status["stage"], "replaced_same_course")
        self.assertEqual(promotion["course_match"], "same_course")

    def test_web_learning_state_api_round_trips_local_store(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                coverage = _request_json(host, port, "GET", f"/api/coverage?course_id={course_id}")
                generated = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/cards/generate",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "overwrite": True,
                        "compile_mode": "fallback",
                    },
                    expected_status=201,
                )
                cards = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/cards?course_id={course_id}&lecture_id={lecture['lecture_id']}",
                )
                note = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/notes",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "body": "RAG uses retrieved evidence.",
                    },
                    expected_status=201,
                )
                bookmark = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/bookmarks",
                    {
                        "course_id": course_id,
                        "target_type": "card",
                        "target_id": cards["cards"][0]["card_id"],
                    },
                    expected_status=201,
                )
                progress = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/progress",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "status": "read",
                    },
                    expected_status=201,
                )
                notes = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/notes?course_id={course_id}&lecture_id={lecture['lecture_id']}",
                )
                bookmarks = _request_json(host, port, "GET", f"/api/bookmarks?course_id={course_id}")
                progress_list = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/progress?course_id={course_id}&lecture_id={lecture['lecture_id']}",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(note["status"], "completed")
        self.assertEqual(coverage["coverage"]["covered_lecture_count"], 1)
        self.assertEqual(generated["generated_card_count"], 1)
        self.assertEqual(cards["card_count"], 1)
        self.assertEqual(cards["cards"][0]["source_segment_ids"], [f"{lecture['lecture_id']}::manual::00001"])
        self.assertEqual(bookmark["status"], "completed")
        self.assertEqual(bookmark["bookmark"]["target_type"], "card")
        self.assertEqual(progress["progress"]["status"], "read")
        self.assertEqual(notes["note_count"], 1)
        self.assertEqual(bookmarks["bookmark_count"], 1)
        self.assertEqual(progress_list["progress"][0]["status"], "read")

    def test_web_course_delete_api_removes_local_course(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                deleted = _request_json(host, port, "DELETE", f"/api/courses?course_id={course_id}")
                courses = _request_json(host, port, "GET", "/api/courses")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(deleted["status"], "completed")
        self.assertTrue(deleted["deleted"])
        self.assertEqual(deleted["course_id"], course_id)
        self.assertEqual(courses["courses"], [])

    def test_web_learning_state_api_rejects_invalid_progress_status(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                payload = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/progress",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "status": "mastered",
                    },
                    expected_status=400,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["error_type"], "ValueError")

    def test_web_guide_api_returns_read_only_guidance(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            store.generate_knowledge_cards(course_id, compile_mode="fallback", compile_provider=None)
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                guide = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/guide?course_id={course_id}&mode=self_check&lecture_id={lecture['lecture_id']}",
                )
                progress = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/progress?course_id={course_id}&lecture_id={lecture['lecture_id']}",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["mode"], "self_check")
        self.assertEqual(guide["question_count"], 1)
        self.assertFalse(guide["limits"]["writes_progress"])
        self.assertFalse(guide["limits"]["creates_study_plan"])
        self.assertFalse(guide["limits"]["scores_learner"])
        self.assertEqual(progress["progress"][0]["status"], "not_started")

    def test_web_chat_stream_returns_typed_sse_events(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
            calls = []

            def fake_stream(**kwargs: object) -> list[dict[str, object]]:
                calls.append(kwargs)
                return [
                    {
                        "event": "route_ready",
                        "id": "",
                        "data": {
                            "payload": {
                                "route": "live_hermes_gateway",
                                "internal_trace_hidden": True,
                            }
                        },
                    },
                    {
                        "event": "teaching_state",
                        "id": "",
                        "data": {
                            "payload": {
                                "progress_ratio_label": "0/1",
                                "knowledge_atoms": [
                                    {
                                        "label": "深度学习入门",
                                        "status": "正在带学",
                                        "focus": "等待你的第一句回答",
                                    }
                                ],
                            }
                        },
                    },
                    {
                        "event": "message_delta",
                        "id": "",
                        "data": {
                            "payload": {
                                "delta": "我来带你从零基础开始。你先用一句话说说：深度学习和普通程序最大的差别是什么？"
                            }
                        },
                    },
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {
                        "event": "thread_state",
                        "id": "web_hermes_test",
                        "data": {"status": "completed", "route": "hermes_frontdesk"},
                    },
                ]

            previous_turn = web_server.build_web_hermes_turn
            previous_events = web_server.build_web_hermes_sse_events
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "我对深度学习是否零基础的，你看与带着我学习完这些问题吗"},
                )
            finally:
                web_server.build_web_hermes_turn = previous_turn
                web_server.build_web_hermes_sse_events = previous_events
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertEqual([event["event"] for event in events[:4]], ["route_ready", "teaching_state", "message_delta", "done"])
        self.assertEqual(events[-1]["event"], "thread_state")
        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.assertEqual(calls[0]["message"], "我对深度学习是否零基础的，你看与带着我学习完这些问题吗")
        self.assertEqual(calls[0]["web_course_id"], course_id)
        self.assertEqual(calls[0]["chat_messages"][-1]["role"], "user")
        self.assertEqual(calls[0]["chat_messages"][-1]["content"], calls[0]["message"])
        self.assertEqual(calls[0]["chat_events"], [])
        self.assertEqual(calls[0]["course_binding"]["child_course_title"], "AI interview course")
        self.assertEqual(calls[0]["course_context"]["course"]["title"], "AI interview course")
        self.assertEqual(calls[0]["course_context"]["lecture"]["title"], "RAG and Agent")
        self.assertNotIn("LiteChatCore", json.dumps(events, ensure_ascii=False))
        self.assertNotIn("no_transcript_evidence", json.dumps(events, ensure_ascii=False))
        self.assertIn("深度学习入门", json.dumps(events, ensure_ascii=False))
        self.assertIn("从零基础开始", events[2]["data"]["payload"]["delta"])

    def test_web_chat_stream_sends_compact_context_and_recent_history_to_hermes(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = build_course_skeleton(
                title="Large systems course",
                source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                video_refs=[
                    {
                        "sequence": index,
                        "bvid": f"BV{index:08d}",
                        "title": f"Lecture {index}",
                        "source_url": f"https://www.bilibili.com/video/BV{index:08d}",
                    }
                    for index in range(1, 12)
                ],
                now="2026-05-14T00:00:00Z",
            )
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            target_lecture = skeleton.lectures[5]
            store.write_transcript_segments(
                skeleton.course.course_id,
                target_lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{target_lecture.lecture_id}::manual::{index:05d}",
                        lecture_id=target_lecture.lecture_id,
                        start_seconds=float(index),
                        end_seconds=float(index + 1),
                        text=f"segment {index} explains cache locality and memory access.",
                    )
                    for index in range(25)
                ],
            )
            store._replace_knowledge_cards(
                skeleton.course.course_id,
                [
                    KnowledgeCardRecord(
                        card_id=f"card_{index:02d}",
                        course_id=skeleton.course.course_id,
                        lecture_id=target_lecture.lecture_id,
                        title=f"Cache atom {index}",
                        body=f"Cache atom body {index}",
                        source_segment_ids=[],
                        tags=[],
                        summary=f"Cache atom summary {index}",
                        review_questions=[f"Check {index}", f"Follow-up {index}", f"Extra {index}"],
                    ).to_dict()
                    for index in range(14)
                ],
            )
            thread = store.create_chat_thread(
                skeleton.course.course_id,
                title="long thread",
                channel="web",
                thread_id="thread_long_history",
            )
            for index in range(14):
                store.append_chat_message(
                    str(thread["thread_id"]),
                    "user" if index % 2 == 0 else "assistant",
                    f"history message {index}",
                    now=f"2026-05-14T00:00:{index:02d}Z",
                )
            for index in range(30):
                store.append_chat_event(
                    str(thread["thread_id"]),
                    "teaching_control",
                    {
                        "current_atom_index": index,
                        "completed_atom_count": index,
                        "total_atom_count": 30,
                        "mastery_signals": {"retrieval": True},
                    },
                    now=f"2026-05-14T00:01:{index:02d}Z",
                )
            calls = []

            def fake_stream(**kwargs: object) -> list[dict[str, object]]:
                calls.append(kwargs)
                return [
                    {"event": "route_ready", "id": "", "data": {"payload": {"route": "live_hermes_gateway"}}},
                    {"event": "message_delta", "id": "", "data": {"payload": {"delta": "Compact reply."}}},
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {"event": "thread_state", "id": "web_hermes_compact", "data": {"status": "completed"}},
                ]

            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread_runner = threading.Thread(target=server.serve_forever, daemon=True)
            thread_runner.start()
            host, port = server.server_address
            try:
                _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {
                        "course_id": skeleton.course.course_id,
                        "thread_id": "thread_long_history",
                        "lecture_sequence": 6,
                        "message": "continue",
                    },
                )
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread_runner.join(timeout=5)

        context = calls[0]["course_context"]
        self.assertLess(len(context["lectures"]), len(skeleton.lectures))
        self.assertEqual([lecture["sequence"] for lecture in context["lectures"]], [4, 5, 6, 7, 8])
        self.assertEqual(len(context["reader"]["segments"]), web_server.CHAT_CONTEXT_READER_SEGMENT_LIMIT)
        self.assertEqual(context["reader"]["segment_count"], 25)
        self.assertEqual(len(context["knowledge_cards"]), web_server.CHAT_CONTEXT_KNOWLEDGE_CARD_LIMIT)
        self.assertEqual(len(calls[0]["chat_messages"]), web_server.CHAT_CONTEXT_HISTORY_MESSAGE_LIMIT + 1)
        self.assertEqual(calls[0]["chat_messages"][-1]["content"], "continue")
        self.assertLessEqual(len(calls[0]["chat_events"]), web_server.CHAT_CONTEXT_HISTORY_EVENT_LIMIT)
        self.assertEqual(calls[0]["chat_events"][-1]["payload"]["current_atom_index"], 29)

    def test_web_chat_stream_passes_bound_course_mapping_to_hermes_adapter(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            store.upsert_web_course_binding(
                course_id,
                binding_status="bound",
                mother_course_id="mother_course_deep_learning",
                mother_node_scope="intro",
                now="2026-05-18T00:00:00Z",
            )
            calls = []

            def fake_stream(**kwargs: object) -> list[dict[str, object]]:
                calls.append(kwargs)
                return [
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {"event": "thread_state", "id": "web_hermes_bound", "data": {"status": "completed"}},
                ]

            previous_turn = web_server.build_web_hermes_turn
            previous_events = web_server.build_web_hermes_sse_events
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "继续这门课"},
                )
            finally:
                web_server.build_web_hermes_turn = previous_turn
                web_server.build_web_hermes_sse_events = previous_events
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.assertEqual(calls[0]["web_course_id"], course_id)
        self.assertEqual(calls[0]["course_binding"]["binding_status"], "bound")
        self.assertEqual(calls[0]["course_binding"]["mother_course_id"], "mother_course_deep_learning")

    def test_web_chat_stream_persists_hermes_turn_to_sqlite_chat_tables(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)

            def fake_stream(**kwargs: object) -> list[dict[str, object]]:
                return [
                    {"event": "route_ready", "id": "", "data": {"payload": {"route": "live_hermes_gateway"}}},
                    {
                        "event": "tool_chain",
                        "id": "",
                        "data": {"payload": {"label": "route", "status": "completed", "detail": "real tool progress"}},
                    },
                    {"event": "message_delta", "id": "", "data": {"payload": {"delta": "Persisted "}}},
                    {"event": "message_delta", "id": "", "data": {"payload": {"delta": "Hermes reply."}}},
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {
                        "event": "thread_state",
                        "id": "api-hermes-session-id",
                        "data": {"status": "completed", "thread": {"thread_id": "api-hermes-session-id"}},
                    },
                ]

            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "start learning"},
                )
                history = _request_json(host, port, "GET", f"/api/chat/history?course_id={course_id}")
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            persisted_store = SQLiteCourseStore(temp_dir)
            threads = persisted_store.list_chat_threads(course_id=course_id, channel="web")
            messages = persisted_store.list_chat_messages(str(threads[0]["thread_id"]))
            persisted_events = persisted_store.list_chat_events(str(threads[0]["thread_id"]))

        self.assertEqual([event["event"] for event in events[:5]], ["route_ready", "tool_chain", "message_delta", "message_delta", "done"])
        self.assertEqual(events[-1]["event"], "thread_state")
        self.assertTrue(events[-1]["data"]["thread"]["local_history_available"])
        self.assertNotIn("thread_id", events[-1]["data"]["thread"])
        self.assertNotIn("course_id", events[-1]["data"]["thread"])
        self.assertNotIn("api-hermes-session-id", json.dumps(events[-1], ensure_ascii=False))
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "start learning")
        self.assertEqual(messages[1]["content"], "Persisted Hermes reply.")
        self.assertIn("message_delta", [event["event_type"] for event in persisted_events])
        self.assertEqual(history["thread"]["thread_id"], threads[0]["thread_id"])
        self.assertEqual([message["role"] for message in history["messages"]], ["user", "assistant"])
        self.assertEqual(history["threads"][0]["message_count"], 2)

    def test_web_chat_stream_sends_visual_evidence_media_for_key_screenshot_request(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            segment = store.read_transcript_segments(course_id, lecture["lecture_id"])[0]
            store.upsert_visual_evidence_records(
                course_id,
                [
                    {
                        "visual_id": "keyframe_test",
                        "lecture_id": lecture["lecture_id"],
                        "segment_id": segment["segment_id"],
                        "title": "关键截图 1",
                        "explanation": "真实关键帧说明",
                        "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
                        "source_url": lecture["source_url"],
                        "provenance": "generated_keyframe anchor=anc_test",
                        "created_at": "2026-05-19T00:00:00Z",
                    }
                ],
            )
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = None
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "message": "发一下这一节的关键截图",
                    },
                )
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            persisted_store = SQLiteCourseStore(temp_dir)
            thread_id = persisted_store.list_chat_threads(course_id=course_id, channel="web")[0]["thread_id"]
            history = persisted_store.list_chat_events(thread_id)

        self.assertEqual(headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertIn("media", [event["event"] for event in events])
        media_event = next(event for event in events if event["event"] == "media")
        self.assertEqual(media_event["data"]["payload"]["visual_id"], "keyframe_test")
        self.assertEqual(media_event["data"]["payload"]["source"], "VISUAL_EVIDENCE")
        self.assertTrue(any(event["event_type"] == "media" for event in history))

    def test_web_chat_stream_blocks_demo_visual_as_key_screenshot(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            store.upsert_visual_evidence_records(
                course_id,
                [
                    {
                        "visual_id": "demo_visual_only",
                        "lecture_id": lecture["lecture_id"],
                        "title": "Demo visual",
                        "explanation": "demo",
                        "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
                        "source_url": lecture["source_url"],
                        "provenance": "demo_visual",
                        "created_at": "2026-05-19T00:00:00Z",
                    }
                ],
            )
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = None
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {
                        "course_id": course_id,
                        "lecture_id": lecture["lecture_id"],
                        "message": "发一下这一节的关键截图",
                    },
                )
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertNotIn("media", [event["event"] for event in events])
        self.assertEqual(events[-1]["data"]["payload"]["status"], "blocked")
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertIn("不能用示意图代替课程截图", serialized)
        self.assertNotIn("demo_visual_only", serialized)

    def test_web_chat_history_can_select_older_thread(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            old_thread = store.create_chat_thread(course_id, title="old learning thread", channel="web")
            store.append_chat_message(str(old_thread["thread_id"]), "user", "old question")
            store.append_chat_message(str(old_thread["thread_id"]), "assistant", "old answer")
            latest_thread = store.create_chat_thread(course_id, title="latest short thread", channel="web")
            store.append_chat_message(str(latest_thread["thread_id"]), "user", "latest question")

            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                selected = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/chat/history?course_id={course_id}&thread_id={old_thread['thread_id']}",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(selected["thread"]["thread_id"], old_thread["thread_id"])
        self.assertEqual([message["content"] for message in selected["messages"]], ["old question", "old answer"])
        counts = {thread["thread_id"]: thread["message_count"] for thread in selected["threads"]}
        self.assertEqual(counts[old_thread["thread_id"]], 2)
        self.assertEqual(counts[latest_thread["thread_id"]], 1)

    def test_public_demo_chat_history_is_visitor_scoped_and_end_session_cleans_only_that_visitor(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            visitor_a_thread = store.create_chat_thread(
                course_id,
                title="visitor a",
                channel="web:visitor:visitor_a",
            )
            store.append_chat_message(str(visitor_a_thread["thread_id"]), "user", "visitor a question")
            visitor_b_thread = store.create_chat_thread(
                course_id,
                title="visitor b",
                channel="web:visitor:visitor_b",
            )
            store.append_chat_message(str(visitor_b_thread["thread_id"]), "user", "visitor b question")
            shared_thread = store.create_chat_thread(course_id, title="old shared", channel="web")
            store.append_chat_message(str(shared_thread["thread_id"]), "user", "old shared question")

            previous_public_demo = web_server.Course2KnowledgeWebHandler.public_demo
            web_server.Course2KnowledgeWebHandler.public_demo = True
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                visitor_a_history = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/chat/history?course_id={course_id}&visitor_session_id=visitor_a",
                )
                visitor_b_history = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/chat/history?course_id={course_id}&visitor_session_id=visitor_b",
                )
                cross_read = _request_json(
                    host,
                    port,
                    "GET",
                    (
                        f"/api/chat/history?course_id={course_id}"
                        f"&visitor_session_id=visitor_a&thread_id={visitor_b_thread['thread_id']}"
                    ),
                    expected_status=400,
                )
                ended = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/chat/session/end",
                    {"course_id": course_id, "visitor_session_id": "visitor_a"},
                )
                visitor_a_after_end = _request_json(
                    host,
                    port,
                    "GET",
                    f"/api/chat/history?course_id={course_id}&visitor_session_id=visitor_a",
                )
            finally:
                web_server.Course2KnowledgeWebHandler.public_demo = previous_public_demo
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            persisted = SQLiteCourseStore(temp_dir)
            remaining_visitor_b_threads = persisted.list_chat_threads(
                course_id=course_id,
                channel="web:visitor:visitor_b",
            )
            remaining_shared_threads = persisted.list_chat_threads(course_id=course_id, channel="web")

        self.assertEqual([item["thread_id"] for item in visitor_a_history["threads"]], [visitor_a_thread["thread_id"]])
        self.assertEqual([item["thread_id"] for item in visitor_b_history["threads"]], [visitor_b_thread["thread_id"]])
        self.assertEqual(visitor_a_history["messages"][0]["content"], "visitor a question")
        self.assertEqual(visitor_b_history["messages"][0]["content"], "visitor b question")
        self.assertEqual(cross_read["status"], "failed")
        self.assertEqual(ended["deleted_thread_count"], 1)
        self.assertEqual(visitor_a_after_end["threads"], [])
        self.assertEqual(remaining_visitor_b_threads[0]["thread_id"], visitor_b_thread["thread_id"])
        self.assertEqual(remaining_shared_threads[0]["thread_id"], shared_thread["thread_id"])

    def test_web_chat_stream_concurrency_limit_returns_429_without_creating_empty_thread(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
            previous_chat_semaphore = web_server._CHAT_SEMAPHORE
            previous_chat_capacity = web_server._CHAT_SEMAPHORE_CAPACITY
            previous_chat_limit_env = web_server.os.environ.get(web_server.CHAT_CONCURRENCY_ENV)
            web_server.os.environ[web_server.CHAT_CONCURRENCY_ENV] = "1"
            web_server._CHAT_SEMAPHORE = threading.BoundedSemaphore(1)
            web_server._CHAT_SEMAPHORE_CAPACITY = 1
            self.assertTrue(web_server._CHAT_SEMAPHORE.acquire(blocking=False))
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                rejected = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "hello"},
                    expected_status=429,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                try:
                    web_server._CHAT_SEMAPHORE.release()
                except ValueError:
                    pass
                web_server._CHAT_SEMAPHORE = previous_chat_semaphore
                web_server._CHAT_SEMAPHORE_CAPACITY = previous_chat_capacity
                if previous_chat_limit_env is None:
                    web_server.os.environ.pop(web_server.CHAT_CONCURRENCY_ENV, None)
                else:
                    web_server.os.environ[web_server.CHAT_CONCURRENCY_ENV] = previous_chat_limit_env

            persisted = SQLiteCourseStore(temp_dir)

        self.assertEqual(rejected["error_type"], "TooManyChatRequests")
        self.assertIn("当前访客较多", rejected["error"])
        self.assertEqual(persisted.list_chat_threads(course_id=course_id, channel="web"), [])

    def test_web_chat_stream_persists_teaching_control_event(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)

            def fake_stream(**_kwargs: object) -> list[dict[str, object]]:
                return [
                    {"event": "route_ready", "id": "", "data": {"payload": {"route": "live_hermes_gateway"}}},
                    {
                        "event": "teaching_state",
                        "id": "",
                        "data": {
                            "payload": {
                                "progress_ratio_label": "2/2",
                                "next_step_label": "进入下一口",
                                "teaching_control": {
                                    "contract": "lite_teaching_convergence_contract",
                                    "position_index": 1,
                                    "passed_count": 1,
                                    "total_count": 2,
                                    "next_step_label": "进入下一口",
                                },
                                "learning_signals": {
                                    "retrieval_signal": True,
                                    "grounded_evidence_signal": True,
                                    "causal_chain_signal": True,
                                    "boundary_signal": True,
                                    "transfer_signal": False,
                                    "overquestioning_risk": False,
                                    "scope_challenge_signal": False,
                                    "same_atom_probe_count": 1,
                                },
                                "knowledge_atoms": [
                                    {
                                        "label": "RAG and Agent boundary",
                                        "status": "已通过",
                                        "focus": "RAG retrieves; Agent acts.",
                                        "state_hint": "passed",
                                    },
                                    {
                                        "label": "Agent tool chain",
                                        "status": "当前口",
                                        "focus": "Plan then call tools.",
                                        "state_hint": "current",
                                    },
                                ],
                            }
                        },
                    },
                    {"event": "message_delta", "id": "", "data": {"payload": {"delta": "Advance to the next bite."}}},
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {"event": "thread_state", "id": "gw-thread", "data": {"status": "completed"}},
                ]

            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "continue"},
                )
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            persisted_store = SQLiteCourseStore(temp_dir)
            threads = persisted_store.list_chat_threads(course_id=course_id, channel="web")
            persisted_events = persisted_store.list_chat_events(str(threads[0]["thread_id"]))

        teaching_state = next(event for event in events if event["event"] == "teaching_state")
        self.assertEqual(teaching_state["data"]["payload"]["knowledge_atoms"][0]["state_hint"], "passed")
        teaching_control = next(event for event in persisted_events if event["event_type"] == "teaching_control")
        self.assertEqual(teaching_control["tool_name"], "hermes_teaching_convergence")
        self.assertEqual(teaching_control["payload"]["current_atom_index"], 1)
        self.assertEqual(teaching_control["payload"]["completed_atom_count"], 1)
        self.assertTrue(teaching_control["payload"]["mastery_signals"]["retrieval"])
        self.assertTrue(teaching_control["payload"]["mastery_signals"]["evidence"])
        self.assertTrue(teaching_control["payload"]["mastery_signals"]["causal"])
        self.assertTrue(teaching_control["payload"]["mastery_signals"]["boundary"])
        self.assertEqual(teaching_control["payload"]["student_visible"]["knowledge_atoms"][1]["state_hint"], "current")
        serialized = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("course_id", serialized)
        self.assertNotIn("node_id", serialized)
        self.assertNotIn("transfer_ready", serialized)
        self.assertNotIn("pseudo_mastery", serialized)

    def test_web_chat_stream_recovers_from_gateway_session_id_as_thread_id(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)

            def fake_stream(**_kwargs: object) -> list[dict[str, object]]:
                return [
                    {"event": "route_ready", "id": "", "data": {"payload": {"route": "live_hermes_gateway"}}},
                    {"event": "message_delta", "id": "", "data": {"payload": {"delta": "Recovered local thread."}}},
                    {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                    {
                        "event": "thread_state",
                        "id": "api-stale-gateway-session",
                        "data": {"status": "completed", "thread": {"thread_id": "api-stale-gateway-session"}},
                    },
                ]

            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = fake_stream
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "thread_id": "api-stale-gateway-session", "message": "continue"},
                )
            finally:
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(events[-1]["event"], "thread_state")
        self.assertTrue(events[-1]["data"]["thread"]["local_history_available"])
        self.assertNotIn("thread_id", events[-1]["data"]["thread"])
        self.assertNotIn("course_id", events[-1]["data"]["thread"])
        self.assertNotIn("api-stale-gateway-session", json.dumps(events[-1], ensure_ascii=False))

    def test_web_hermes_stream_emits_student_safe_runtime_metrics(self) -> None:
        adapter = load_web_hermes_adapter_module()

        def fake_gateway(**_kwargs: object) -> list[dict[str, object]]:
            return [
                {
                    "type": "tool_progress",
                    "payload": {"tool": "studio_office_teaching_route", "status": "completed"},
                },
                {"type": "delta", "delta": "Metric-safe reply."},
                {"type": "done", "session_id": "gateway-thread", "had_text": True},
            ]

        previous_gateway = adapter.stream_hermes_gateway
        adapter.stream_hermes_gateway = fake_gateway
        try:
            events = list(
                adapter.stream_web_hermes_sse_events(
                    message="start learning",
                    thread_id="local-thread",
                    channel="web",
                    web_course_id="course_public",
                    course_binding={"binding_status": "unbound", "child_course_title": "Public course"},
                    course_context={
                        "course": {"title": "Public course"},
                        "lecture": {"title": "Lecture one"},
                        "knowledge_cards": [
                            {
                                "title": "Cache locality",
                                "summary": "Cache favors nearby repeated memory access.",
                                "body": "Cache locality means nearby data is likely reused soon.",
                            }
                        ],
                    },
                    chat_messages=[{"role": "user", "content": "start learning"}],
                    chat_events=[],
                )
            )
        finally:
            adapter.stream_hermes_gateway = previous_gateway

        metric_events = [event for event in events if event["event"] == "runtime_metric"]
        self.assertGreaterEqual(len(metric_events), 3)
        self.assertIn("message_delta", [event["event"] for event in events])
        self.assertEqual(events[-1]["event"], "thread_state")
        metric_payload = metric_events[-1]["data"]["payload"]
        self.assertEqual(metric_payload["stage"], "stream_done")
        self.assertGreater(metric_payload["prompt_chars"], 0)
        self.assertGreater(metric_payload["teaching_packet_chars"], 0)
        self.assertGreaterEqual(metric_payload["route_ms"], 0)
        self.assertGreaterEqual(metric_payload["first_delta_ms"], 0)
        serialized = json.dumps(metric_events, ensure_ascii=False)
        self.assertNotIn("course_id", serialized)
        self.assertNotIn("node_id", serialized)
        self.assertNotIn("thread_id", serialized)
        self.assertNotIn("queue_id", serialized)

    def test_web_chat_stream_rejects_missing_hermes_adapter(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
            previous_turn = web_server.build_web_hermes_turn
            previous_events = web_server.build_web_hermes_sse_events
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.build_web_hermes_turn = None
            web_server.build_web_hermes_sse_events = None
            web_server.stream_web_hermes_sse_events = None
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                payload = _request_json(
                    host,
                    port,
                    "POST",
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "我对深度学习是否零基础的"},
                    expected_status=400,
                )
            finally:
                web_server.build_web_hermes_turn = previous_turn
                web_server.build_web_hermes_sse_events = previous_events
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(payload["status"], "failed")
        self.assertIn("Hermes Web frontdesk adapter", payload["error"])

    def test_web_chat_stream_blocks_missing_visual_without_raw_path_leak(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
            previous_turn = web_server.build_web_hermes_turn
            previous_events = web_server.build_web_hermes_sse_events
            previous_stream = web_server.stream_web_hermes_sse_events
            web_server.stream_web_hermes_sse_events = lambda **_kwargs: [
                {
                    "event": "route_ready",
                    "id": "",
                    "data": {"payload": {"route": "live_hermes_gateway"}},
                },
                {
                    "event": "teaching_state",
                    "id": "",
                    "data": {"payload": {"knowledge_atoms": [{"label": "Hermes 节点", "status": "正在带学"}]}},
                },
                {
                    "event": "message_delta",
                    "id": "",
                    "data": {"payload": {"delta": "我们先从一个小问题开始：你觉得深度学习是在学规则，还是在学表示？"}},
                },
                {"event": "done", "id": "", "data": {"payload": {"status": "completed"}}},
                {"event": "thread_state", "id": "web_hermes_safe", "data": {"status": "completed"}},
            ]
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                _headers, events = _request_sse(
                    host,
                    port,
                    "/api/chat/stream",
                    {"course_id": course_id, "message": "show visual C:/private/image.png"},
                )
            finally:
                web_server.build_web_hermes_turn = previous_turn
                web_server.build_web_hermes_sse_events = previous_events
                web_server.stream_web_hermes_sse_events = previous_stream
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        serialized = json.dumps(events, ensure_ascii=False)
        self.assertEqual([event["event"] for event in events[:4]], ["route_ready", "teaching_state", "message_delta", "done"])
        self.assertNotIn("C:/private/image.png", serialized)
        self.assertNotIn("no_transcript_evidence", serialized)
        for blocked_term in ("mastery", "review_stage", "queue", "diagnosis", "feedback"):
            self.assertNotIn(blocked_term, serialized.lower())

    def test_web_chat_panel_assets_wire_to_stream_endpoint(self) -> None:
        index_html = (ROOT / "apps" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "apps" / "web" / "static" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "apps" / "web" / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("\u4e92\u52a8", index_html)
        self.assertIn("\u8bfe\u7a0b\u7ba1\u7406", index_html)
        self.assertIn("\u8bfe\u7a0b\u7b14\u8bb0", index_html)
        self.assertIn("\u5b66\u4e60\u52a9\u624b", index_html)
        self.assertIn('data-view="interaction"', index_html)
        self.assertIn('data-view="courses"', index_html)
        self.assertIn('data-view="notes"', index_html)
        self.assertIn('id="view-interaction"', index_html)
        self.assertIn('id="view-courses"', index_html)
        self.assertIn('id="view-notes"', index_html)
        self.assertIn('id="bilibili-cookie"', index_html)
        self.assertIn('id="paste-cookie-button"', index_html)
        self.assertIn('id="clear-cookie-button"', index_html)
        self.assertIn("bilibili_cookie", app_js)
        self.assertIn("renderImportStatusCard", app_js)
        self.assertIn("effectiveImportStatus", app_js)
        self.assertIn("importPhaseCopy", app_js)
        self.assertIn("importProgressCounts", app_js)
        self.assertIn("importTimeline", app_js)
        self.assertIn("restoreLatestImportStatus", app_js)
        self.assertIn("/api/import/status", app_js)
        self.assertIn("/api/runtime", app_js)
        self.assertIn("is-public-demo", app_js)
        self.assertIn("renderPublicDemoReadonlyCard", app_js)
        self.assertIn("Public demo is read-only", app_js)
        self.assertIn("readonly-demo-card", app_js)
        self.assertIn("readonly-pill", app_js)
        self.assertIn(".readonly-demo-card", styles)
        self.assertIn(".readonly-pill", styles)
        self.assertIn("导入进度", app_js)
        self.assertIn("正在生成笔记、知识原子和关口", app_js)
        self.assertIn("入库保护阻断", app_js)
        self.assertIn("新课程已合并入本地库", app_js)
        self.assertIn("同课程重导入已更新", app_js)
        self.assertIn("B 站页面没有返回可用字幕元数据", app_js)
        self.assertIn(".import-progress-track", styles)
        self.assertIn(".import-alert", styles)
        self.assertIn(".import-timeline", styles)
        self.assertIn("interaction-layout", index_html)
        self.assertIn("side-stack", index_html)
        self.assertIn('id="atom-state-list"', index_html)
        self.assertIn('id="atom-progress-summary"', index_html)
        self.assertIn('id="learning-signal-list"', index_html)
        self.assertIn('id="lesson-advance-panel"', index_html)
        self.assertIn('id="lesson-advance-button"', index_html)
        self.assertIn("下一节课", index_html)
        for old_nav_label in (
            "<span>\u4eca\u65e5\u6559\u5ba4</span>",
            "<span>\u8bfe\u7a0b\u5e93</span>",
            "<span>\u5b66\u4e60\u8d44\u6599</span>",
            "<span>\u8fde\u63a5\u65b9\u5f0f</span>",
        ):
            self.assertNotIn(old_nav_label, index_html)
        for old_panel_label in ("\u5feb\u901f\u67e5\u8d44\u6599", "\u5f15\u7528\u95ee\u7b54", "\u4e0b\u4e00\u6b65"):
            self.assertNotIn(old_panel_label, index_html)
        self.assertNotIn('data-view="adapter"', index_html)
        self.assertNotIn('id="view-adapter"', index_html)
        self.assertIn('id="chat-log"', index_html)
        self.assertIn('id="chat-input"', index_html)
        self.assertIn('id="chat-thread-select"', index_html)
        self.assertIn("开始学习当前课程", index_html)
        self.assertIn("chat-actions", index_html)
        self.assertIn('id="chat-send-button"', index_html)
        self.assertIn('"/api/chat/stream"', app_js)
        self.assertIn("parseSse", app_js)
        self.assertIn("renderChatEvents", app_js)
        self.assertIn("renderChatThreadSelect", app_js)
        self.assertIn("chatThreadLabel", app_js)
        self.assertIn("refreshChatThreads", app_js)
        self.assertIn("runtime_metric", app_js)
        self.assertIn("renderChatWaitingState", app_js)
        self.assertIn("createChatWaitingController", app_js)
        self.assertIn("isLikelyPublicDemoHost", app_js)
        self.assertIn("shouldUsePublicDemoLoadingCopy", app_js)
        self.assertIn("setCourseLoadingStatus", app_js)
        self.assertIn("正在准备示例课程，约 3-8 秒", app_js)
        self.assertIn("示例课程准备好后，可以直接向学习助手提问", app_js)
        self.assertIn("示例课程已准备好，可以直接和学习助手对话", app_js)
        self.assertIn('id="experience-guide"', index_html)
        self.assertIn("云端演示可以体验", app_js)
        self.assertIn("示例课程浏览、课堂笔记阅读、知识节点状态、Hermes 学习对话", app_js)
        self.assertIn("本地部署后可体验", app_js)
        self.assertIn("B 站课程导入、扫码 / Cookie 登录态", app_js)
        self.assertIn("experience-guide", styles)
        self.assertIn("正在判断目前知识点状态", app_js)
        self.assertIn("Hermes 正在真实调用 studio_office_teaching_route", app_js)
        self.assertIn("通常需要 3-6 秒", app_js)
        self.assertIn("无需重复发送你的问题", app_js)
        self.assertIn("当前访客较多，请稍后再试", app_js)
        self.assertIn("appendRuntimeMetricEvent", app_js)
        self.assertIn("loadChatHistory(thread.thread_id)", app_js)
        self.assertIn("renderAtomStates", app_js)
        self.assertIn("renderHermesTeachingState", app_js)
        self.assertIn("renderLearningSignals", app_js)
        self.assertIn("renderPersistedTeachingControl", app_js)
        self.assertIn("normalizePersistedLearningSignals", app_js)
        self.assertIn("renderLessonAdvance", app_js)
        self.assertIn("hasCompletedHermesAtoms", app_js)
        self.assertIn("advanceToNextLecture", app_js)
        self.assertIn("nextLecture", app_js)
        self.assertIn("state.currentHermesAtoms = atoms", app_js)
        self.assertIn("hermesAtomClass(atom) === \"is-passed\"", app_js)
        self.assertIn("selectLecture(targetLecture.sequence)", app_js)
        self.assertIn("payload.events", app_js)
        self.assertIn('event.event_type === "teaching_control"', app_js)
        self.assertIn("markAtomsFromText", app_js)
        self.assertIn("Hermes 教学前台", app_js)
        self.assertIn("任意 B 站课程", app_js)
        self.assertIn('event.key === "Enter" && !event.shiftKey && !event.isComposing', app_js)
        self.assertIn("event.preventDefault()", app_js)
        self.assertIn('eventsWrap.innerHTML = "";', app_js)
        self.assertNotIn("我对深度学习是否零基础", index_html)
        self.assertNotIn("我对深度学习是否零基础", app_js)
        server_py = (ROOT / "apps" / "web" / "server.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("build_web_hermes_turn", server_py)
        self.assertIn("stream_web_hermes_sse_events", server_py)
        self.assertIn("from course2knowledge_lite_store.web_hermes import", server_py)
        self.assertIn("Hermes Web frontdesk adapter is unavailable", server_py)
        self.assertNotIn("MOTHER_REPO_ROOT", server_py)
        self.assertNotIn("from studio", server_py)
        self.assertNotIn("import studio", server_py)
        self.assertIn("Hermes Lite 是可选工具前台", readme)
        self.assertIn("业务权威仍然在本地 SQLite runtime", readme)
        self.assertIn("Web Lite 与 Hermes Lite 只读取或调用同一个 runtime", readme)
        self.assertIn("Markdown / Obsidian \u5185\u5bb9\u672a\u63a5\u5165\u6216\u672a\u751f\u6210", app_js)
        self.assertIn("markdownToHtml", app_js)
        self.assertIn("generated_note_", app_js)
        self.assertIn("markdown-rendered", app_js)
        self.assertIn(".markdown-rendered", styles)
        self.assertIn('setView("interaction")', app_js)
        self.assertIn(".chat-panel", styles)
        self.assertIn(".thread-select-label", styles)
        self.assertIn(".chat-actions", styles)
        self.assertIn(".chat-message", styles)
        self.assertIn(".chat-waiting", styles)
        self.assertIn(".chat-waiting-detail", styles)
        self.assertIn(".chat-event.is-runtime_metric", styles)
        self.assertIn(".interaction-layout", styles)
        self.assertIn(".side-stack", styles)
        self.assertIn(".atom-item", styles)
        self.assertIn(".learning-signal", styles)
        self.assertIn(".lesson-advance-panel", styles)
        forbidden_static = "\n".join([index_html, styles]).lower()
        for blocked_term in ("mastery", "review_stage", "diagnosis", "feedback"):
            self.assertNotIn(blocked_term, forbidden_static)

    def test_web_hermes_frontdesk_is_vendored_in_lite_package_without_mother_import(self) -> None:
        server_py = (ROOT / "apps" / "web" / "server.py").read_text(encoding="utf-8")
        tool_chain = (
            ROOT
            / "packages"
            / "course-store"
            / "src"
            / "course2knowledge_lite_store"
            / "web_hermes"
            / "tool_chain.py"
        ).read_text(encoding="utf-8")
        office_route = (
            ROOT
            / "packages"
            / "course-store"
            / "src"
            / "course2knowledge_lite_store"
            / "office_route.py"
        ).read_text(encoding="utf-8")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        combined_runtime = "\n".join([server_py, tool_chain, office_route])
        for forbidden in ("MOTHER_REPO_ROOT", "from studio", "import studio", "studio.frontdesk", "studio.common"):
            self.assertNotIn(forbidden, combined_runtime)
        self.assertIn("from course2knowledge_lite_store.web_hermes import", server_py)
        self.assertIn("course2knowledge_lite_store.office_route", tool_chain)
        self.assertIn('"data_store_authority": "child_local_sqlite"', office_route)
        self.assertIn('"private_mother_state_allowed": False', office_route)
        self.assertIn("course2knowledge_lite_store/web_hermes", pyproject)
        self.assertIn("course2knowledge_lite_store/office_route.py", pyproject)

    def test_web_import_status_copy_distinguishes_merge_replace_and_blocked(self) -> None:
        app_js = (ROOT / "apps" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("merged_new_course", app_js)
        self.assertIn("replaced_same_course", app_js)
        self.assertIn("新课程已合并入本地库", app_js)
        self.assertIn("同课程重导入已更新", app_js)
        self.assertIn("入库保护阻断", app_js)
        self.assertIn("临时库已就绪", app_js)

    def test_web_serves_public_docs_assets_for_chat_media(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            web_server.Course2KnowledgeWebHandler.store_root = Path(temp_dir)
            server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.Course2KnowledgeWebHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            try:
                connection = HTTPConnection(host, port, timeout=10)
                connection.request("GET", "/docs/assets/visual-evidence/rag-agent-flow.png")
                response = connection.getresponse()
                content_type = response.getheader("Content-Type")
                body = response.read()
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 200)
        self.assertEqual(content_type, "image/png")
        self.assertGreater(len(body), 100)

    def test_web_exposes_visual_evidence_api_and_notes_renderer(self) -> None:
        app_js = (ROOT / "apps" / "web" / "static" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "apps" / "web" / "static" / "styles.css").read_text(encoding="utf-8")
        server_py = (ROOT / "apps" / "web" / "server.py").read_text(encoding="utf-8")

        self.assertIn('/api/visuals', server_py)
        self.assertIn("loadVisualEvidence", app_js)
        self.assertIn("generated_keyframe", app_js)
        self.assertIn("visual-evidence-block", app_js)
        self.assertIn(".visual-grid", styles)


def _store_with_transcript(temp_dir: str) -> tuple[SQLiteCourseStore, str]:
    skeleton = build_course_skeleton(
        title="AI interview course",
        source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
        video_refs=[
            {
                "sequence": 1,
                "bvid": "BV00000001",
                "title": "RAG and Agent",
                "source_url": "https://www.bilibili.com/video/BV00000001",
            }
        ],
        now="2026-05-14T00:00:00Z",
    )
    lecture = skeleton.lectures[0]
    store = SQLiteCourseStore(temp_dir)
    store.write_skeleton(skeleton)
    store.write_transcript_segments(
        skeleton.course.course_id,
        lecture.lecture_id,
        [
            TranscriptSegmentRecord(
                segment_id=f"{lecture.lecture_id}::manual::00001",
                lecture_id=lecture.lecture_id,
                start_seconds=0.0,
                end_seconds=6.0,
                text="RAG retrieves course evidence, while an Agent plans actions and calls tools.",
            )
        ],
    )
    return store, skeleton.course.course_id


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status: int = 200):
        self.payload = payload
        self.status = status

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class _FakeBilibiliQrOpener:
    def __init__(self, cookie_jar: object, calls: list[str]):
        self.cookie_jar = cookie_jar
        self.calls = calls

    def open(self, request: object, timeout: int = 20) -> _FakeHttpResponse:
        del timeout
        url = getattr(request, "full_url", "")
        self.calls.append(str(url))
        if "qrcode/generate" in str(url):
            return _FakeHttpResponse(
                {
                    "code": 0,
                    "data": {
                        "url": "https://account.bilibili.com/h5/account-h5/auth/qr",
                        "qrcode_key": "fake-qrcode-key",
                    },
                }
            )
        if "qrcode/poll" in str(url):
            self.cookie_jar.set_cookie(
                Cookie(
                    version=0,
                    name="SESSDATA",
                    value="secret-session",
                    port=None,
                    port_specified=False,
                    domain=".bilibili.com",
                    domain_specified=True,
                    domain_initial_dot=True,
                    path="/",
                    path_specified=True,
                    secure=False,
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
            self.cookie_jar.set_cookie(
                Cookie(
                    version=0,
                    name="bili_jct",
                    value="secret-csrf",
                    port=None,
                    port_specified=False,
                    domain=".bilibili.com",
                    domain_specified=True,
                    domain_initial_dot=True,
                    path="/",
                    path_specified=True,
                    secure=False,
                    expires=None,
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
            )
            return _FakeHttpResponse({"code": 0, "data": {"code": 0, "message": "扫码登录成功"}})
        return _FakeHttpResponse({"code": -1, "message": "unexpected url"})


def _request_json(
    host: str,
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    *,
    expected_status: int = 200,
) -> dict[str, object]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    connection = HTTPConnection(host, port, timeout=10)
    try:
        connection.request(
            method,
            path,
            body=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        response = connection.getresponse()
        raw_body = response.read().decode("utf-8")
    finally:
        connection.close()
    if response.status != expected_status:
        raise AssertionError(f"expected HTTP {expected_status}, got {response.status}: {raw_body}")
    result = json.loads(raw_body)
    if not isinstance(result, dict):
        raise AssertionError(f"expected object response, got {type(result).__name__}")
    return result


def _request_sse(
    host: str,
    port: int,
    path: str,
    payload: dict[str, object],
    *,
    expected_status: int = 200,
) -> tuple[dict[str, str], list[dict[str, object]]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    connection = HTTPConnection(host, port, timeout=10)
    try:
        connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw_body = response.read().decode("utf-8")
        headers = {key.lower(): value for key, value in response.getheaders()}
    finally:
        connection.close()
    if response.status != expected_status:
        raise AssertionError(f"expected HTTP {expected_status}, got {response.status}: {raw_body}")
    return headers, _parse_sse(raw_body)


def _parse_sse(raw_body: str) -> list[dict[str, object]]:
    events = []
    for block in raw_body.strip().split("\n\n"):
        event_type = ""
        event_id = ""
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("id: "):
                event_id = line.removeprefix("id: ")
            elif line.startswith("data: "):
                data_lines.append(line.removeprefix("data: "))
        if event_type:
            events.append(
                {
                    "event": event_type,
                    "id": event_id,
                    "data": json.loads("\n".join(data_lines) or "{}"),
                }
            )
    return events


if __name__ == "__main__":
    unittest.main()
