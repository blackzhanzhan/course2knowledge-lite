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

from course2knowledge_lite_store import JsonCourseStore, TranscriptSegmentRecord, build_course_skeleton  # noqa: E402


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
            paths = JsonCourseStore(store_root).write_skeleton(skeleton)
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


def _store_with_transcript(temp_dir: str) -> tuple[JsonCourseStore, str]:
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
    store = JsonCourseStore(temp_dir)
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


if __name__ == "__main__":
    unittest.main()
