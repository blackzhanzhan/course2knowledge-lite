from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_store.lecture_dossier import build_lite_lecture_dossier  # noqa: E402
from course2knowledge_lite_store.models import TranscriptSegmentRecord  # noqa: E402
from course2knowledge_lite_store.skeleton import build_course_skeleton  # noqa: E402
from course2knowledge_lite_store.sqlite_store import SQLiteCourseStore  # noqa: E402
from course2knowledge_lite_store.multimodal import (  # noqa: E402
    MultimodalConfigError,
    build_lite_visual_evidence_records,
    build_lite_anchor_frame_windows,
    copy_lite_keyframes_to_public_assets,
    extract_lite_candidate_frames_for_windows,
    format_anchor_timestamp,
    parse_anchor_timestamp,
    require_ffmpeg,
    select_lite_keyframes,
)


class LiteMultimodalTests(unittest.TestCase):
    def test_builds_frame_windows_from_lite_dossier_anchors(self) -> None:
        dossier = build_lite_lecture_dossier(
            lecture={
                "lecture_id": "course_demo::lecture::001",
                "title": "RAG accuracy",
                "source_url": "https://www.bilibili.com/video/BV00000001",
            },
            segments=[
                {
                    "segment_id": "seg_001",
                    "lecture_id": "course_demo::lecture::001",
                    "start_seconds": 9.0,
                    "end_seconds": 13.0,
                    "text": "RAG retrieves course evidence before answering.",
                },
                {
                    "segment_id": "seg_002",
                    "lecture_id": "course_demo::lecture::001",
                    "start_seconds": 24.0,
                    "end_seconds": 29.0,
                    "text": "The agent then decides whether it needs a tool call.",
                },
            ],
            compile_mode="fallback",
            compile_provider=None,
        )

        windows = build_lite_anchor_frame_windows(
            anchors=dossier.to_dict()["anchors"],
            lead_seconds=2.0,
            lag_seconds=4.0,
        )

        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].source_segment_ids, ("seg_001",))
        self.assertEqual(windows[0].source_line_ids, (1,))
        self.assertEqual(windows[0].suggested_timestamp, "00:00:09")
        self.assertEqual(windows[0].center_seconds, 9.0)
        self.assertEqual(windows[0].start_seconds, 7.0)
        self.assertEqual(windows[0].end_seconds, 13.0)
        self.assertIn("RAG retrieves", windows[0].evidence_quote)
        self.assertEqual(windows[0].to_dict()["source_segment_ids"], ["seg_001"])

    def test_timestamp_parser_accepts_hms_ms_and_mmss(self) -> None:
        self.assertEqual(parse_anchor_timestamp("00:01:02.500"), 62.5)
        self.assertEqual(parse_anchor_timestamp("01:02"), 62.0)
        self.assertEqual(parse_anchor_timestamp("00:00:00,250"), 0.25)
        self.assertEqual(format_anchor_timestamp(62.5), "00:01:02.500")
        self.assertEqual(format_anchor_timestamp(62), "00:01:02")

    def test_invalid_anchor_timestamp_fails_loudly(self) -> None:
        with self.assertRaises(MultimodalConfigError):
            parse_anchor_timestamp("not-a-time")

    def test_anchor_without_screenshot_timestamp_is_skipped(self) -> None:
        windows = build_lite_anchor_frame_windows(
            anchors=[
                {"anchor_id": "no_time", "evidence_quote": "missing timestamp"},
                {
                    "anchor_id": "ok",
                    "suggested_screenshot_timestamp": "00:00:02",
                    "evidence_quote": "has timestamp",
                },
            ]
        )

        self.assertEqual([window.anchor_id for window in windows], ["ok"])

    def test_sqlite_upserts_visual_evidence_without_dropping_other_records(self) -> None:
        skeleton = build_course_skeleton(
            title="Demo course",
            source_url="https://space.bilibili.com/111/lists/222?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "Lecture 1",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Lecture 2",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-19T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            segment_id = f"{skeleton.lectures[0].lecture_id}::seg::001"
            store.write_transcript_segments(
                skeleton.course.course_id,
                skeleton.lectures[0].lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=skeleton.lectures[0].lecture_id,
                        start_seconds=0.0,
                        end_seconds=2.0,
                        text="A visual anchor should bind to a real segment.",
                    )
                ],
            )
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    {
                        "visual_id": "demo_visual",
                        "lecture_id": skeleton.lectures[1].lecture_id,
                        "title": "Demo visual",
                        "explanation": "Existing demo visual",
                        "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
                        "source_url": skeleton.lectures[1].source_url,
                        "provenance": "demo_visual",
                        "created_at": "2026-05-19T00:00:00Z",
                    }
                ],
            )

            store.upsert_visual_evidence_records(
                skeleton.course.course_id,
                [
                    {
                        "visual_id": "keyframe_001",
                        "lecture_id": skeleton.lectures[0].lecture_id,
                        "segment_id": segment_id,
                        "title": "关键截图 1",
                        "explanation": "generated",
                        "image_path": "docs/assets/generated-keyframes/course/lecture/keyframe.jpg",
                        "source_url": skeleton.lectures[0].source_url,
                        "provenance": "generated_keyframe anchor=anc_001",
                        "created_at": "2026-05-19T00:01:00Z",
                    }
                ],
            )
            visuals = store.list_visual_evidence(course_id=skeleton.course.course_id)

        self.assertEqual([item["visual_id"] for item in visuals], ["keyframe_001", "demo_visual"])
        self.assertIn("generated_keyframe", visuals[0]["provenance"])

    def test_sqlite_backfills_visual_keyframe_status_without_counting_demo_visuals(self) -> None:
        skeleton = build_course_skeleton(
            title="Demo course",
            source_url="https://space.bilibili.com/111/lists/222?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "Lecture 1",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                {
                    "sequence": 2,
                    "bvid": "BV00000002",
                    "title": "Lecture 2",
                    "source_url": "https://www.bilibili.com/video/BV00000002",
                },
            ],
            now="2026-05-19T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            store.write_skeleton(skeleton)
            run = store.create_import_run(
                course_id=skeleton.course.course_id,
                source_url=skeleton.course.source_url,
                status="partial",
                stage="ready_gate_blocked",
                total_lectures=2,
                completed_lectures=1,
                failed_lectures=1,
                now="2026-05-19T00:00:00Z",
            )
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    {
                        "visual_id": "keyframe_001",
                        "lecture_id": skeleton.lectures[0].lecture_id,
                        "title": "关键截图 1",
                        "explanation": "generated",
                        "image_path": "docs/assets/generated-keyframes/course/lecture/keyframe.jpg",
                        "source_url": skeleton.lectures[0].source_url,
                        "provenance": "generated_keyframe anchor=anc_001",
                        "created_at": "2026-05-19T00:01:00Z",
                    },
                    {
                        "visual_id": "demo_visual",
                        "lecture_id": skeleton.lectures[1].lecture_id,
                        "title": "Demo visual",
                        "explanation": "Existing demo visual",
                        "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
                        "source_url": skeleton.lectures[1].source_url,
                        "provenance": "demo_visual",
                        "created_at": "2026-05-19T00:00:00Z",
                    },
                ],
            )

            result = store.backfill_visual_keyframe_status(
                skeleton.course.course_id,
                run_id=run["run_id"],
                now="2026-05-19T00:02:00Z",
            )
            repeated = store.backfill_visual_keyframe_status(
                skeleton.course.course_id,
                run_id=run["run_id"],
                now="2026-05-19T00:03:00Z",
            )
            artifacts = store.list_import_artifacts(run_id=run["run_id"], artifact_type="visual_keyframes")

        self.assertEqual(result["ready_visual_keyframe_lecture_count"], 1)
        self.assertEqual(result["unavailable_visual_keyframe_lecture_count"], 1)
        self.assertEqual(repeated["ready_visual_keyframe_lecture_count"], 1)
        self.assertEqual(len(artifacts), 2)
        by_lecture = {artifact["lecture_id"]: artifact for artifact in artifacts}
        self.assertEqual(by_lecture[skeleton.lectures[0].lecture_id]["status"], "ready")
        self.assertEqual(by_lecture[skeleton.lectures[0].lecture_id]["payload"]["provenance"], "generated_keyframe")
        self.assertEqual(by_lecture[skeleton.lectures[1].lecture_id]["status"], "unavailable")
        self.assertEqual(by_lecture[skeleton.lectures[1].lecture_id]["payload"]["reason"], "missing_source_media")
        self.assertEqual(by_lecture[skeleton.lectures[1].lecture_id]["payload"]["demo_visual_count"], 1)

    def test_extracts_candidate_frames_from_real_local_media(self) -> None:
        ffmpeg = require_ffmpeg()
        with tempfile.TemporaryDirectory() as temp_dir:
            media_path = Path(temp_dir) / "input.mp4"
            output_root = Path(temp_dir) / "frames"
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=160x90:rate=10:duration=3",
                    "-pix_fmt",
                    "yuv420p",
                    str(media_path),
                ],
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            windows = build_lite_anchor_frame_windows(
                anchors=[
                    {
                        "anchor_id": "anchor/001",
                        "suggested_screenshot_timestamp": "00:00:01",
                        "source_segment_ids": ["seg_001"],
                        "source_line_ids": [1],
                        "evidence_quote": "frame proof",
                    }
                ],
                lead_seconds=0.2,
                lag_seconds=0.6,
            )

            frames = extract_lite_candidate_frames_for_windows(
                media_path=str(media_path),
                windows=windows,
                output_root=str(output_root),
                sample_every_seconds=0.25,
            )
            selected = select_lite_keyframes(frames)
            copied = copy_lite_keyframes_to_public_assets(
                keyframes=selected,
                repo_root=temp_dir,
                course_id="course_demo",
                lecture_id="course_demo::lecture::001",
            )
            records = build_lite_visual_evidence_records(
                course_id="course_demo",
                lecture={
                    "lecture_id": "course_demo::lecture::001",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                },
                anchors=[
                    {
                        "anchor_id": "anchor/001",
                        "suggested_screenshot_timestamp": "00:00:01",
                        "source_segment_ids": ["seg_001"],
                        "evidence_quote": "frame proof",
                    }
                ],
                keyframe_paths=copied,
                now="2026-05-19T00:00:00Z",
            )

            self.assertIn("anchor/001", frames)
            self.assertGreaterEqual(len(frames["anchor/001"]), 1)
            for frame_path in frames["anchor/001"]:
                self.assertTrue(Path(frame_path).exists())
                self.assertGreater(Path(frame_path).stat().st_size, 0)
            self.assertIn("anchor/001", selected)
            self.assertIn("anchor/001", copied)
            self.assertTrue((Path(temp_dir) / copied["anchor/001"]).exists())
            self.assertEqual(records[0]["segment_id"], "seg_001")
            self.assertEqual(records[0]["image_path"], copied["anchor/001"])
            self.assertIn("generated_keyframe", records[0]["provenance"])


if __name__ == "__main__":
    unittest.main()
