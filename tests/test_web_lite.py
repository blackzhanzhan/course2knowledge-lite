from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
