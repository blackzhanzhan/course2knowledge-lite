from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_guidance import get_learning_guide  # noqa: E402
from course2knowledge_lite_store import (  # noqa: E402
    JsonCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_course_skeleton,
)


class GuidedLearningTests(unittest.TestCase):
    def test_continue_selects_next_unread_transcript_backed_lecture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lectures = _guided_store(temp_dir)
            store.set_reading_progress(course_id, lectures[0].lecture_id, "read", now="2026-05-14T01:00:00Z")
            before_progress = store.list_reading_progress(course_id=course_id)

            guide = get_learning_guide(store=store, course_id=course_id, mode="continue")

            self.assertEqual(store.list_reading_progress(course_id=course_id), before_progress)

        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["mode"], "continue")
        self.assertEqual(guide["lecture"]["sequence"], 2)
        self.assertEqual(guide["recommendation"]["action"], "continue_lecture")
        self.assertFalse(guide["limits"]["writes_progress"])
        self.assertFalse(guide["limits"]["creates_study_plan"])
        self.assertFalse(guide["limits"]["scores_learner"])

    def test_walkthrough_combines_segments_cards_and_visuals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lectures = _guided_store(temp_dir)

            guide = get_learning_guide(
                store=store,
                course_id=course_id,
                mode="walkthrough",
                lecture_id=lectures[0].lecture_id,
            )

        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["mode"], "walkthrough")
        self.assertGreaterEqual(len(guide["walkthrough"]), 3)
        self.assertEqual(len(guide["evidence"]["segment_citations"]), 2)
        self.assertEqual(len(guide["evidence"]["cards"]), 2)
        self.assertEqual(len(guide["evidence"]["visual_evidence"]), 1)
        self.assertEqual(guide["evidence"]["visual_evidence"][0]["visual_id"], "visual_rag_agent_flow")
        self.assertFalse(guide["limits"]["external_llm_used"])

    def test_self_check_questions_are_source_linked_without_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lectures = _guided_store(temp_dir)

            guide = get_learning_guide(
                store=store,
                course_id=course_id,
                mode="self_check",
                lecture_id=lectures[0].lecture_id,
                limit=2,
            )

        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["question_count"], 2)
        self.assertEqual(guide["questions"][0]["source_card"]["lecture_id"], lectures[0].lecture_id)
        self.assertTrue(guide["questions"][0]["citations"])
        self.assertFalse(guide["grading"]["automatic_grading"])
        self.assertFalse(guide["grading"]["mastery_judgment"])
        self.assertFalse(guide["limits"]["diagnoses_mastery"])
        self.assertFalse(guide["limits"]["spaced_review_queue"])

    def test_recap_exposes_key_points_and_next_target_without_private_loops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lectures = _guided_store(temp_dir)

            guide = get_learning_guide(
                store=store,
                course_id=course_id,
                mode="recap",
                lecture_id=lectures[0].lecture_id,
            )

        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["mode"], "recap")
        self.assertGreaterEqual(len(guide["recap"]["key_points"]), 2)
        self.assertEqual(guide["recap"]["next_reading_target"]["sequence"], 2)
        self.assertFalse(guide["limits"]["creates_schedule"])
        self.assertFalse(guide["limits"]["exercise_feedback"])
        self.assertNotIn("score", guide["recap"])
        self.assertNotIn("schedule", guide["recap"])

    def test_invalid_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, _lectures = _guided_store(temp_dir)

            with self.assertRaisesRegex(ValueError, "mode must be one of"):
                get_learning_guide(store=store, course_id=course_id, mode="daily_plan")


def _guided_store(temp_dir: str) -> tuple[JsonCourseStore, str, list[object]]:
    skeleton = build_course_skeleton(
        title="AI interview course",
        source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
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
                "title": "Vector search",
                "source_url": "https://www.bilibili.com/video/BV00000002",
            },
            {
                "sequence": 3,
                "bvid": "BV00000003",
                "title": "Deployment",
                "source_url": "https://www.bilibili.com/video/BV00000003",
            },
        ],
        now="2026-05-14T00:00:00Z",
    )
    store = JsonCourseStore(temp_dir)
    store.write_skeleton(skeleton)
    first = skeleton.lectures[0]
    second = skeleton.lectures[1]
    first_segment_one = f"{first.lecture_id}::manual::00001"
    first_segment_two = f"{first.lecture_id}::manual::00002"
    store.write_transcript_segments(
        skeleton.course.course_id,
        first.lecture_id,
        [
            TranscriptSegmentRecord(
                segment_id=first_segment_one,
                lecture_id=first.lecture_id,
                start_seconds=0.0,
                end_seconds=6.0,
                text="RAG retrieves evidence before answering a course question.",
            ),
            TranscriptSegmentRecord(
                segment_id=first_segment_two,
                lecture_id=first.lecture_id,
                start_seconds=6.0,
                end_seconds=12.0,
                text="An Agent plans tool calls, while RAG keeps the answer grounded in retrieved context.",
            ),
        ],
    )
    store.write_transcript_segments(
        skeleton.course.course_id,
        second.lecture_id,
        [
            TranscriptSegmentRecord(
                segment_id=f"{second.lecture_id}::manual::00001",
                lecture_id=second.lecture_id,
                start_seconds=0.0,
                end_seconds=8.0,
                text="Vector search compares embeddings to retrieve relevant course segments.",
            )
        ],
    )
    cards = store.generate_knowledge_cards(skeleton.course.course_id)["cards"]
    store.write_visual_evidence_records(
        skeleton.course.course_id,
        [
            VisualEvidenceRecord(
                visual_id="visual_rag_agent_flow",
                course_id=skeleton.course.course_id,
                lecture_id=first.lecture_id,
                segment_id=first_segment_one,
                card_id=cards[0]["card_id"],
                title="RAG and Agent flow",
                explanation="RAG grounds answers in retrieved evidence; Agent plans tool use around that evidence.",
                image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                source_url=first.source_url,
                provenance="public demo diagram derived from transcript segment",
                created_at="2026-05-15T00:00:00Z",
            )
        ],
    )
    return store, skeleton.course.course_id, skeleton.lectures


if __name__ == "__main__":
    unittest.main()
