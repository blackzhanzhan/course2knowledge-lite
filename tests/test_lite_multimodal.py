from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_store.lecture_dossier import build_lite_lecture_dossier  # noqa: E402
from course2knowledge_lite_store.multimodal import (  # noqa: E402
    MultimodalConfigError,
    build_lite_anchor_frame_windows,
    format_anchor_timestamp,
    parse_anchor_timestamp,
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
        )

        windows = build_lite_anchor_frame_windows(
            anchors=dossier.to_dict()["anchors"],
            lead_seconds=2.0,
            lag_seconds=4.0,
        )

        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].source_segment_ids, ("seg_001",))
        self.assertEqual(windows[0].source_line_ids, (1,))
        self.assertEqual(windows[0].suggested_timestamp, "00:09")
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


if __name__ == "__main__":
    unittest.main()
