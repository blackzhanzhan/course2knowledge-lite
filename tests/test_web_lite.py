from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER = ROOT / "apps" / "web" / "server.py"
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_store import (  # noqa: E402
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


class WebLiteTests(unittest.TestCase):
    def test_web_import_api_writes_collection_skeleton_and_returns_receipt(self) -> None:
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
            paths = SQLiteCourseStore(store_root).write_skeleton(skeleton)
            return {
                "course": skeleton.course.to_dict(),
                "lectures": [lecture.to_dict() for lecture in skeleton.lectures],
                "import_status": skeleton.import_status.to_dict(),
                "paths": paths,
            }

        previous_import = web_server.import_collection_skeleton_to_store
        web_server.import_collection_skeleton_to_store = fake_import
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
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        finally:
            web_server.import_collection_skeleton_to_store = previous_import

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["lecture_count"], 2)
        self.assertEqual(payload["import_status"]["stage"], "collection_expanded")
        self.assertEqual(len(courses["courses"]), 1)
        self.assertEqual(courses["courses"][0]["lecture_count"], 2)

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
            store.generate_knowledge_cards(course_id)
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
                    {"course_id": course_id, "message": "What is RAG Agent?"},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertEqual([event["event"] for event in events[:4]], ["tool_start", "tool_result", "message_delta", "done"])
        self.assertEqual(events[-1]["event"], "thread_state")
        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.assertEqual(events[1]["data"]["payload"]["hit_count"], 1)
        self.assertIn("RAG retrieves course evidence", events[2]["data"]["payload"]["delta"])

    def test_web_chat_stream_emits_media_from_visual_evidence(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_transcript(temp_dir)
            lecture = store.read_lectures(course_id)[0]
            card = store.generate_knowledge_cards(course_id)["cards"][0]
            store.write_visual_evidence_records(
                course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=course_id,
                        lecture_id=str(lecture["lecture_id"]),
                        segment_id=f"{lecture['lecture_id']}::manual::00001",
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=str(lecture["source_url"]),
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
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
                    {"course_id": course_id, "message": "Show visual RAG Agent"},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        media = next(event for event in events if event["event"] == "media")
        self.assertEqual(media["data"]["payload"]["source"], "VISUAL_EVIDENCE")
        self.assertEqual(media["data"]["payload"]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(media["data"]["payload"]["image_path"], "docs/assets/visual-evidence/rag-agent-flow.png")

    def test_web_chat_stream_blocks_missing_visual_without_raw_path_leak(self) -> None:
        web_server = load_web_server_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            _store, course_id = _store_with_transcript(temp_dir)
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
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        serialized = json.dumps(events, ensure_ascii=False)
        self.assertEqual([event["event"] for event in events[:4]], ["tool_start", "tool_result", "error", "done"])
        self.assertEqual(events[-1]["data"]["status"], "blocked")
        self.assertIn("[redacted-path]", serialized)
        self.assertNotIn("C:/private/image.png", serialized)
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
        self.assertIn("interaction-layout", index_html)
        self.assertIn("side-stack", index_html)
        self.assertIn('id="atom-state-list"', index_html)
        self.assertIn('id="atom-progress-summary"', index_html)
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
        self.assertIn('id="chat-send-button"', index_html)
        self.assertIn('"/api/chat/stream"', app_js)
        self.assertIn("parseSse", app_js)
        self.assertIn("renderChatEvents", app_js)
        self.assertIn("renderAtomStates", app_js)
        self.assertIn("markAtomsFromText", app_js)
        self.assertIn("Markdown / Obsidian \u5185\u5bb9\u672a\u63a5\u5165\u6216\u672a\u751f\u6210", app_js)
        self.assertIn('setView("interaction")', app_js)
        self.assertIn(".chat-panel", styles)
        self.assertIn(".chat-message", styles)
        self.assertIn(".interaction-layout", styles)
        self.assertIn(".side-stack", styles)
        self.assertIn(".atom-item", styles)
        forbidden_static = "\n".join([index_html, styles]).lower()
        for blocked_term in ("mastery", "review_stage", "diagnosis", "feedback"):
            self.assertNotIn(blocked_term, forbidden_static)

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
