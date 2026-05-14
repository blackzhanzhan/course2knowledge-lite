from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "qa" / "src"))

from course2knowledge_lite_qa import answer_course_question  # noqa: E402
from course2knowledge_lite_store import JsonCourseStore, TranscriptSegmentRecord, build_course_skeleton  # noqa: E402


class CitationQaTests(unittest.TestCase):
    def test_answer_course_question_uses_transcript_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_rag_agent_transcript(temp_dir)

            answer = answer_course_question(
                store=store,
                course_id=course_id,
                question="RAG 和 Agent 的区别是什么？",
            )

        self.assertEqual(answer["status"], "answered")
        self.assertEqual(answer["citation_count"], 1)
        self.assertFalse(answer["limits"]["external_llm_used"])
        self.assertIn("RAG", answer["answer"])
        self.assertEqual(answer["citations"][0]["lecture_sequence"], 1)
        self.assertIn("RAG Agent", answer["query"])

    def test_answer_course_question_blocks_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id = _store_with_rag_agent_transcript(temp_dir)

            answer = answer_course_question(
                store=store,
                course_id=course_id,
                question="向量数据库怎么选型？",
            )

        self.assertEqual(answer["status"], "blocked")
        self.assertEqual(answer["reason"], "no_transcript_evidence")
        self.assertEqual(answer["citation_count"], 0)
        self.assertFalse(answer["limits"]["external_llm_used"])


def _store_with_rag_agent_transcript(temp_dir: str) -> tuple[JsonCourseStore, str]:
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
                text="RAG retrieves course evidence before answering, while an Agent plans actions and calls tools.",
            )
        ],
    )
    return store, skeleton.course.course_id


if __name__ == "__main__":
    unittest.main()
