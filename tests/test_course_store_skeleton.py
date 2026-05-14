from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_bilibili import BilibiliCollection, BilibiliVideoRef  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_store import JsonCourseStore, TranscriptSegmentRecord, build_course_skeleton  # noqa: E402


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
            store = JsonCourseStore(temp_dir)
            lectures = store.read_lectures(result["course"]["course_id"])

        self.assertEqual(result["course"]["title"], "AI interview course")
        self.assertEqual(result["import_status"]["stage"], "collection_expanded")
        self.assertEqual(len(result["lectures"]), 2)
        self.assertEqual(len(lectures), 2)
        self.assertEqual(lectures[1]["source_id"], "BV00000002")

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


if __name__ == "__main__":
    unittest.main()
