from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_bilibili import BilibiliCollection, BilibiliVideoRef  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_store import (  # noqa: E402
    JsonCourseStore,
    SQLiteCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_course_skeleton,
)


class CourseStoreSkeletonTests(unittest.TestCase):
    def test_bilibili_collection_video_refs_write_course_skeleton(self) -> None:
        collection = BilibiliCollection(
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            title="合集·AI大模型面试-全套合集",
            videos=[
                BilibiliVideoRef(
                    sequence=i,
                    bvid=f"BV{i:08d}",
                    title=f"Lecture {i}",
                    source_url=f"https://www.bilibili.com/video/BV{i:08d}",
                )
                for i in range(1, 31)
            ],
        )

        skeleton = build_course_skeleton(
            title=collection.title,
            source_url=collection.source_url,
            video_refs=collection.videos,
            now="2026-05-14T00:00:00Z",
        )

        self.assertEqual(skeleton.course.import_status, "accepted")
        self.assertEqual(len(skeleton.lectures), 30)
        self.assertEqual(skeleton.lectures[0].sequence, 1)
        self.assertEqual(skeleton.lectures[0].source_id, "BV00000001")
        self.assertEqual(skeleton.import_status.stage, "collection_expanded")
        self.assertEqual(skeleton.import_status.completed_lectures, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = JsonCourseStore(temp_dir).write_skeleton(skeleton)
            store = JsonCourseStore(temp_dir)
            course = store.read_course(skeleton.course.course_id)
            lectures = store.read_lectures(skeleton.course.course_id)
            status = store.read_import_status(skeleton.import_status.import_id)

        self.assertTrue(paths["course"].endswith("course.json"))
        self.assertEqual(course["title"], "合集·AI大模型面试-全套合集")
        self.assertEqual(len(lectures), 30)
        self.assertEqual(lectures[-1]["source_url"], "https://www.bilibili.com/video/BV00000030")
        self.assertEqual(status["total_lectures"], 30)

    def test_handoff_imports_collection_skeleton_to_store(self) -> None:
        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            del api_url, params, referer
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "AI interview course"},
                    "archives": [
                        {"bvid": "BV00000001", "title": "Lecture 1"},
                        {"bvid": "BV00000002", "title": "Lecture 2"},
                    ],
                    "page": {"total": 2},
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_fetch_json,
            )
            store = SQLiteCourseStore(temp_dir)
            lectures = store.read_lectures(result["course"]["course_id"])

        self.assertEqual(result["course"]["title"], "AI interview course")
        self.assertEqual(result["import_status"]["stage"], "collection_expanded")
        self.assertEqual(len(result["lectures"]), 2)
        self.assertEqual(len(lectures), 2)
        self.assertEqual(lectures[1]["source_id"], "BV00000002")

    def test_sqlite_store_round_trips_public_course_records(self) -> None:
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
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            paths = store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            card = store.generate_knowledge_cards(skeleton.course.course_id)["cards"][0]
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            note = store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "RAG uses retrieved evidence.",
                note_id="note_sqlite",
                now="2026-05-14T01:00:00Z",
            )
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "card",
                card["card_id"],
                bookmark_id="bookmark_sqlite",
                now="2026-05-14T01:10:00Z",
            )
            progress = store.set_reading_progress(
                skeleton.course.course_id,
                lecture.lecture_id,
                "read",
                now="2026-05-14T01:15:00Z",
            )

            persisted = SQLiteCourseStore(temp_dir)
            course = persisted.read_course(skeleton.course.course_id)
            lectures = persisted.read_lectures(skeleton.course.course_id)
            search_hits = persisted.search_transcripts(skeleton.course.course_id, "RAG Agent")
            visuals = persisted.list_visual_evidence(course_id=skeleton.course.course_id, query="evidence")
            notes = persisted.list_notes(course_id=skeleton.course.course_id)
            bookmarks = persisted.list_bookmarks(course_id=skeleton.course.course_id)
            conn = sqlite3.connect(paths["database"])
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            finally:
                conn.close()

        self.assertTrue(paths["database"].endswith("course2knowledge-lite.sqlite3"))
        self.assertEqual(course["title"], "AI interview course")
        self.assertEqual(lectures[0]["read_status"], "read")
        self.assertEqual(search_hits[0]["citation"]["segment_id"], segment_id)
        self.assertEqual(visuals[0]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(note["note_id"], "note_sqlite")
        self.assertEqual(bookmark["target_id"], card["card_id"])
        self.assertEqual(progress["status"], "read")
        self.assertEqual(notes[0]["note_id"], "note_sqlite")
        self.assertEqual(bookmarks[0]["bookmark_id"], "bookmark_sqlite")
        self.assertTrue(
            {
                "courses",
                "lectures",
                "transcript_segments",
                "knowledge_cards",
                "visual_evidence",
                "notes",
                "bookmarks",
                "reading_progress",
                "import_statuses",
            }.issubset(tables)
        )

    def test_lecture_reader_and_search_consume_transcript_segments(self) -> None:
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
                    "title": "Tool calling",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        lecture_id = skeleton.lectures[0].lecture_id

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{lecture_id}::manual::00001",
                        lecture_id=lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="This segment explains the difference between RAG and Agent workflows.",
                    )
                ],
            )

            reader = store.read_lecture_reader(skeleton.course.course_id, lecture_sequence=1)
            results = store.search_transcripts(skeleton.course.course_id, "RAG Agent")

        self.assertTrue(reader["has_transcript"])
        self.assertEqual(reader["segment_count"], 1)
        self.assertEqual(reader["lecture"]["title"], "RAG and Agent")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["citation"]["lecture_sequence"], 1)
        self.assertEqual(results[0]["citation"]["segment_id"], f"{lecture_id}::manual::00001")
        self.assertIn("RAG", results[0]["snippet"])

    def test_transcript_coverage_summarizes_covered_and_missing_lectures(self) -> None:
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
                    "title": "RAG accuracy",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
                {
                    "sequence": 3,
                    "bvid": "BV00000003",
                    "title": "Learning route",
                    "source_url": "https://www.bilibili.com/video/BV00000003",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            for lecture in skeleton.lectures[:2]:
                store.write_transcript_segments(
                    skeleton.course.course_id,
                    lecture.lecture_id,
                    [
                        TranscriptSegmentRecord(
                            segment_id=f"{lecture.lecture_id}::manual::00001",
                            lecture_id=lecture.lecture_id,
                            start_seconds=0.0,
                            end_seconds=6.0,
                            text=f"{lecture.title} transcript segment",
                        )
                    ],
                )

            coverage = store.summarize_transcript_coverage(skeleton.course.course_id)

        self.assertEqual(coverage["lecture_count"], 3)
        self.assertEqual(coverage["covered_lecture_count"], 2)
        self.assertEqual(coverage["missing_lecture_count"], 1)
        self.assertEqual(coverage["total_segment_count"], 2)
        self.assertAlmostEqual(coverage["coverage_ratio"], 0.6667)
        self.assertTrue(coverage["lectures"][0]["has_transcript"])
        self.assertFalse(coverage["lectures"][2]["has_transcript"])

    def test_learning_state_round_trips_notes_bookmarks_and_progress(self) -> None:
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
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves course evidence, while an Agent plans actions and calls tools.",
                    )
                ],
            )

            note = store.create_note(
                skeleton.course.course_id,
                lecture.lecture_id,
                "RAG uses retrieved evidence.",
                note_id="note_test",
                now="2026-05-14T01:00:00Z",
            )
            updated_note = store.update_note(
                skeleton.course.course_id,
                "note_test",
                "RAG grounds answers in retrieved evidence.",
                now="2026-05-14T01:05:00Z",
            )
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "segment",
                segment_id,
                bookmark_id="bookmark_test",
                now="2026-05-14T01:10:00Z",
            )
            progress = store.set_reading_progress(
                skeleton.course.course_id,
                lecture.lecture_id,
                "read",
                now="2026-05-14T01:15:00Z",
            )
            persisted = JsonCourseStore(temp_dir)
            persisted_notes = persisted.list_notes(course_id=skeleton.course.course_id, lecture_id=lecture.lecture_id)
            persisted_bookmarks = persisted.list_bookmarks(course_id=skeleton.course.course_id)
            persisted_progress = persisted.get_reading_progress(skeleton.course.course_id, lecture.lecture_id)
            lectures = persisted.read_lectures(skeleton.course.course_id)

        self.assertEqual(note["note_id"], "note_test")
        self.assertEqual(updated_note["body"], "RAG grounds answers in retrieved evidence.")
        self.assertEqual(bookmark["target_id"], segment_id)
        self.assertEqual(progress["status"], "read")
        self.assertEqual(len(persisted_notes), 1)
        self.assertEqual(persisted_notes[0]["updated_at"], "2026-05-14T01:05:00Z")
        self.assertEqual(len(persisted_bookmarks), 1)
        self.assertEqual(persisted_progress["status"], "read")
        self.assertEqual(lectures[0]["read_status"], "read")

    def test_source_linked_knowledge_cards_generate_list_read_and_bookmark(self) -> None:
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
                    "title": "Evaluation",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-14T00:00:00Z",
        )
        first_lecture = skeleton.lectures[0]
        second_lecture = skeleton.lectures[1]
        first_segment_id = f"{first_lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                first_lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=first_segment_id,
                        lecture_id=first_lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            store.write_transcript_segments(
                skeleton.course.course_id,
                second_lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=f"{second_lecture.lecture_id}::manual::00001",
                        lecture_id=second_lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="Evaluation checks whether answers stay grounded in course transcripts.",
                    )
                ],
            )

            result = store.generate_knowledge_cards(skeleton.course.course_id)
            cards = store.list_knowledge_cards(course_id=skeleton.course.course_id)
            first_card = store.read_knowledge_card(skeleton.course.course_id, cards[0]["card_id"])
            bookmark = store.create_bookmark(
                skeleton.course.course_id,
                "card",
                first_card["card_id"],
                bookmark_id="bookmark_card",
                now="2026-05-14T01:20:00Z",
            )
            lecture_cards = store.list_knowledge_cards(
                course_id=skeleton.course.course_id,
                lecture_id=first_lecture.lecture_id,
            )
            first_only = store.generate_knowledge_cards(
                skeleton.course.course_id,
                lecture_id=first_lecture.lecture_id,
                overwrite=True,
            )
            regenerated = store.generate_knowledge_cards(skeleton.course.course_id, overwrite=False)

        self.assertEqual(result["generated_card_count"], 2)
        self.assertEqual(result["card_count"], 2)
        self.assertEqual(len(cards), 2)
        self.assertEqual(first_card["source_segment_ids"], [first_segment_id])
        self.assertEqual(first_card["course_id"], skeleton.course.course_id)
        self.assertIn("RAG", first_card["tags"])
        self.assertEqual(bookmark["target_type"], "card")
        self.assertEqual(bookmark["target_id"], first_card["card_id"])
        self.assertEqual(len(lecture_cards), 1)
        self.assertEqual(first_only["card_count"], 2)
        self.assertEqual(first_only["generated_card_count"], 1)
        self.assertEqual(regenerated["card_count"], 2)

    def test_visual_evidence_is_course_bound_and_queryable(self) -> None:
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
        segment_id = f"{lecture.lecture_id}::manual::00001"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves evidence before an Agent calls tools.",
                    )
                ],
            )
            card = store.generate_knowledge_cards(skeleton.course.course_id)["cards"][0]
            path = store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_rag_agent_flow",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id=card["card_id"],
                        title="RAG and Agent flow",
                        explanation="RAG grounds answers in retrieved evidence; Agent plans tool use around that evidence.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            all_visuals = store.list_visual_evidence(course_id=skeleton.course.course_id)
            query_visuals = store.list_visual_evidence(course_id=skeleton.course.course_id, query="tool use")
            selected = store.select_visual_evidence(course_id=skeleton.course.course_id, query="rag")

        self.assertTrue(path.endswith("visual_evidence.json"))
        self.assertEqual(len(all_visuals), 1)
        self.assertEqual(query_visuals[0]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(selected["segment_id"], segment_id)
        self.assertEqual(selected["card_id"], card["card_id"])
        self.assertFalse(Path(selected["image_path"]).is_absolute())

    def test_visual_evidence_rejects_naked_absolute_image_paths(self) -> None:
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

        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            with self.assertRaisesRegex(ValueError, "repo-local relative path"):
                store.write_visual_evidence_records(
                    skeleton.course.course_id,
                    [
                        {
                            "visual_id": "visual_bad",
                            "course_id": skeleton.course.course_id,
                            "lecture_id": lecture.lecture_id,
                            "title": "Bad image",
                            "explanation": "This should be blocked.",
                            "image_path": "C:/private/image.png",
                            "provenance": "bad path",
                            "created_at": "2026-05-15T00:00:00Z",
                        }
                    ],
                )

    def test_public_visual_evidence_fixture_paths_exist(self) -> None:
        store = JsonCourseStore(ROOT / "data" / "course-store")
        visuals = store.list_visual_evidence(course_id="course_e4af83f2c407")
        selected = store.select_visual_evidence(course_id="course_e4af83f2c407", query="Agent")

        self.assertGreaterEqual(len(visuals), 2)
        self.assertEqual(selected["visual_id"], "visual_rag_agent_flow")
        for item in visuals:
            image_path = str(item["image_path"])
            self.assertFalse(Path(image_path).is_absolute())
            self.assertNotIn("..", Path(image_path).parts)
            self.assertTrue((ROOT / image_path).exists(), image_path)

    def test_reading_progress_rejects_unknown_status(self) -> None:
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
        with tempfile.TemporaryDirectory() as temp_dir:
            store = JsonCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            with self.assertRaisesRegex(ValueError, "status must be one of"):
                store.set_reading_progress(skeleton.course.course_id, skeleton.lectures[0].lecture_id, "mastered")


if __name__ == "__main__":
    unittest.main()
