from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_store import (  # noqa: E402
    LiteChatCore,
    SQLiteCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_course_skeleton,
)


class LiteChatCoreTests(unittest.TestCase):
    def test_sqlite_chat_tables_and_records_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, _lecture_id = _chat_store(temp_dir)
            thread = store.create_chat_thread(
                course_id,
                title="RAG chat",
                thread_id="thread_roundtrip",
                now="2026-05-17T00:00:00Z",
            )
            message = store.append_chat_message(
                thread["thread_id"],
                "user",
                "What is RAG?",
                message_id="message_roundtrip",
                now="2026-05-17T00:00:01Z",
            )
            event = store.append_chat_event(
                thread["thread_id"],
                "tool_start",
                {"tool": "transcript_search"},
                message_id=message["message_id"],
                tool_name="transcript_search",
                event_id="event_roundtrip",
                now="2026-05-17T00:00:02Z",
            )
            persisted = SQLiteCourseStore(temp_dir)
            threads = persisted.list_chat_threads(course_id=course_id, channel="web")
            messages = persisted.list_chat_messages(thread["thread_id"])
            events = persisted.list_chat_events(thread["thread_id"])
            conn = sqlite3.connect(store.db_path)
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            finally:
                conn.close()

        self.assertEqual(threads[0]["thread_id"], "thread_roundtrip")
        self.assertEqual(messages[0]["message_id"], "message_roundtrip")
        self.assertEqual(events[0], event)
        self.assertTrue({"chat_threads", "chat_messages", "chat_events"}.issubset(tables))

    def test_search_turn_emits_typed_events_and_persists_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, _lecture_id = _chat_store(temp_dir)
            turn = LiteChatCore(store).run_turn(
                course_id=course_id,
                message="What is RAG Agent?",
                now="2026-05-17T00:01:00Z",
            )
            persisted_messages = store.list_chat_messages(turn["thread"]["thread_id"])
            persisted_events = store.list_chat_events(turn["thread"]["thread_id"])

        self.assertEqual(turn["status"], "completed")
        self.assertEqual(turn["route"], "search")
        self.assertEqual([item["event_type"] for item in turn["events"]], ["tool_start", "tool_result", "message_delta", "done"])
        self.assertEqual([item["role"] for item in persisted_messages], ["user", "assistant"])
        self.assertEqual(persisted_events, turn["events"])
        self.assertIn("RAG retrieves evidence", turn["assistant_message"]["content"])
        self.assertEqual(turn["events"][1]["payload"]["hit_count"], 1)

    def test_no_evidence_turn_is_blocked_without_private_learning_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, _lecture_id = _chat_store(temp_dir)
            turn = LiteChatCore(store).run_turn(
                course_id=course_id,
                message="What is something absent?",
                now="2026-05-17T00:02:00Z",
            )

        serialized = json.dumps(turn, ensure_ascii=False, sort_keys=True).lower()
        self.assertEqual(turn["status"], "blocked")
        self.assertEqual([item["event_type"] for item in turn["events"]], ["tool_start", "tool_result", "error", "done"])
        self.assertEqual(turn["events"][2]["payload"]["reason"], "no_transcript_evidence")
        for blocked_term in ("mastery", "review_stage", "queue", "diagnosis", "feedback"):
            self.assertNotIn(blocked_term, serialized)

    def test_visual_turn_emits_media_only_from_visual_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lecture_id = _chat_store(temp_dir)
            card = store.generate_knowledge_cards(
                course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"][0]
            store.write_visual_evidence_records(
                course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=course_id,
                        lecture_id=lecture_id,
                        segment_id=f"{lecture_id}::manual::00001",
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url="https://www.bilibili.com/video/BV00000001",
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            turn = LiteChatCore(store).run_turn(
                course_id=course_id,
                message="Show visual RAG Agent",
                now="2026-05-17T00:03:00Z",
            )

        media = next(item for item in turn["events"] if item["event_type"] == "media")
        self.assertEqual(turn["status"], "completed")
        self.assertEqual(turn["route"], "visual_evidence")
        self.assertEqual(media["payload"]["source"], "VISUAL_EVIDENCE")
        self.assertEqual(media["payload"]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(media["payload"]["image_path"], "docs/assets/visual-evidence/rag-agent-flow.png")

    def test_local_routes_cover_guide_cards_and_notes_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store, course_id, lecture_id = _chat_store(temp_dir)
            store.create_note(
                course_id,
                lecture_id,
                "RAG uses retrieved evidence.",
                note_id="note_chat",
                now="2026-05-17T00:04:00Z",
            )
            store.set_reading_progress(course_id, lecture_id, "read", now="2026-05-17T00:04:01Z")
            core = LiteChatCore(store)
            guide = core.run_turn(course_id=course_id, message="continue", now="2026-05-17T00:05:00Z")
            cards = core.run_turn(course_id=course_id, message="show cards", now="2026-05-17T00:06:00Z")
            notes = core.run_turn(course_id=course_id, message="show notes progress", now="2026-05-17T00:07:00Z")

        self.assertEqual(guide["route"], "guide")
        self.assertEqual(guide["events"][1]["tool_name"], "lite_learning_guide")
        self.assertEqual(cards["route"], "cards")
        self.assertEqual(cards["events"][1]["payload"]["card_count"], 1)
        self.assertEqual(notes["route"], "notes_progress")
        self.assertEqual(notes["events"][1]["payload"]["note_count"], 1)
        self.assertEqual(notes["events"][1]["payload"]["reading_progress"][0]["status"], "read")


def _chat_store(temp_dir: str) -> tuple[SQLiteCourseStore, str, str]:
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
    store = SQLiteCourseStore(temp_dir)
    store.write_skeleton(skeleton)
    lecture = skeleton.lectures[0]
    store.write_transcript_segments(
        skeleton.course.course_id,
        lecture.lecture_id,
        [
            TranscriptSegmentRecord(
                segment_id=f"{lecture.lecture_id}::manual::00001",
                lecture_id=lecture.lecture_id,
                start_seconds=0.0,
                end_seconds=6.0,
                text="RAG retrieves evidence before an Agent calls tools.",
            )
        ],
    )
    return store, skeleton.course.course_id, lecture.lecture_id


if __name__ == "__main__":
    unittest.main()
