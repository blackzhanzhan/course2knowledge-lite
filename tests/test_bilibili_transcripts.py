from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_bilibili import fetch_bilibili_timed_subtitles  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_lecture_transcript_by_reference_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_lecture_transcript_to_store  # noqa: E402
from course2knowledge_lite_bilibili import probe_lecture_transcript_source_by_reference  # noqa: E402
from course2knowledge_lite_store import JsonCourseStore  # noqa: E402
import course2knowledge_lite_bilibili.subtitles as subtitles_module  # noqa: E402


def fake_bilibili_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
    del referer
    if api_url.endswith("/x/web-interface/view"):
        return {
            "code": 0,
            "data": {
                "aid": 1001,
                "title": "Lecture 1",
                "pages": [{"page": 1, "cid": 2001, "part": "Lecture 1"}],
            },
        }
    if api_url.endswith("/x/player/wbi/v2") or api_url.endswith("/x/player/v2"):
        self_cid = params.get("cid")
        return {
            "code": 0,
            "data": {
                "subtitle": {
                    "subtitles": [
                        {
                            "lan": "ai-zh",
                            "subtitle_url": f"https://subtitle.example/{self_cid}.json",
                        }
                    ]
                }
            },
        }
    if api_url.startswith("https://subtitle.example/"):
        return {
            "body": [
                {"from": 0.08, "to": 3.32, "content": "first line"},
                {"from": 3.32, "to": 4.5, "content": "second line"},
            ]
        }
    raise AssertionError(f"unexpected api_url: {api_url}")


class BilibiliTranscriptTests(unittest.TestCase):
    def test_default_fetcher_uses_runtime_cookie_env_without_storing_it(self) -> None:
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return b'{"code":0,"data":{}}'

        def fake_urlopen(request, timeout):
            captured["cookie"] = request.headers.get("Cookie")
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.dict("os.environ", {"BILIBILI_COOKIE": "PUBLIC_TEST_COOKIE=fake"}, clear=True), patch.object(
            subtitles_module,
            "urlopen",
            side_effect=fake_urlopen,
        ):
            subtitles_module._default_json_fetcher("https://api.example/path", {"q": "1"}, "https://ref.example")

        self.assertEqual(captured["cookie"], "PUBLIC_TEST_COOKIE=fake")
        self.assertEqual(captured["timeout"], 30)

    def test_fetch_bilibili_timed_subtitles_normalizes_segments(self) -> None:
        bundle = fetch_bilibili_timed_subtitles(
            "https://www.bilibili.com/video/BV00000001",
            fetch_json=fake_bilibili_fetch_json,
        )

        self.assertEqual(bundle.source_id, "BV00000001")
        self.assertEqual(bundle.video_title, "Lecture 1")
        self.assertEqual(len(bundle.timed_lines), 2)
        self.assertEqual(bundle.timed_lines[0]["start_seconds"], 0.08)
        self.assertEqual(bundle.timed_lines[0]["text"], "first line")

    def test_import_lecture_transcript_to_store_writes_segments(self) -> None:
        lecture = {
            "lecture_id": "course_demo::lecture::001",
            "source_url": "https://www.bilibili.com/video/BV00000001",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_lecture_transcript_to_store(
                store_root=temp_dir,
                course_id="course_demo",
                lecture=lecture,
                fetch_json=fake_bilibili_fetch_json,
            )
            segments = JsonCourseStore(temp_dir).read_transcript_segments("course_demo", lecture["lecture_id"])

        self.assertEqual(result["segment_count"], 2)
        self.assertTrue(result["path"].endswith(".segments.json"))
        self.assertEqual(segments[0]["segment_id"], "course_demo::lecture::001::seg::00001")
        self.assertEqual(segments[1]["text"], "second line")

    def test_import_lecture_transcript_by_reference_resolves_import_sequence(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [{"title": "Lecture 1", "bvid": "BV00000001"}],
                        "page": {"total": 1},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
            )
            result = import_lecture_transcript_by_reference_to_store(
                store_root=temp_dir,
                import_id=skeleton["import_status"]["import_id"],
                lecture_sequence=1,
                fetch_json=fake_collection_and_subtitle_fetch,
            )
            segments = JsonCourseStore(temp_dir).read_transcript_segments(
                skeleton["course"]["course_id"],
                result["lecture_id"],
            )

        self.assertEqual(result["course_id"], skeleton["course"]["course_id"])
        self.assertEqual(result["import_id"], skeleton["import_status"]["import_id"])
        self.assertEqual(result["lecture"]["sequence"], 1)
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(segments[0]["text"], "first line")

    def test_probe_lecture_transcript_source_by_reference_reports_available_source(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [{"title": "Lecture 1", "bvid": "BV00000001"}],
                        "page": {"total": 1},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
            )
            result = probe_lecture_transcript_source_by_reference(
                store_root=temp_dir,
                import_id=skeleton["import_status"]["import_id"],
                lecture_sequence=1,
                fetch_json=fake_collection_and_subtitle_fetch,
            )

        self.assertEqual(result["course_id"], skeleton["course"]["course_id"])
        self.assertEqual(result["lecture"]["sequence"], 1)
        self.assertTrue(result["subtitle_source"]["available"])
        self.assertEqual(result["subtitle_source"]["selected_language"], "ai-zh")
        self.assertNotIn("BILIBILI_COOKIE=", json.dumps(result, ensure_ascii=False))

    def test_probe_lecture_transcript_source_by_reference_reports_missing_source(self) -> None:
        def fake_missing_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [{"title": "Lecture 1", "bvid": "BV00000001"}],
                        "page": {"total": 1},
                    },
                }
            if api_url.endswith("/x/player/wbi/v2") or api_url.endswith("/x/player/v2"):
                return {"code": 0, "data": {"subtitle": {"subtitles": []}}}
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_missing_subtitle_fetch,
            )
            result = probe_lecture_transcript_source_by_reference(
                store_root=temp_dir,
                import_id=skeleton["import_status"]["import_id"],
                lecture_sequence=1,
                fetch_json=fake_missing_subtitle_fetch,
            )

        self.assertFalse(result["subtitle_source"]["available"])
        self.assertEqual(result["subtitle_source"]["error_type"], "RuntimeError")
        self.assertIn("Bilibili page did not expose subtitle metadata", result["subtitle_source"]["error"])


if __name__ == "__main__":
    unittest.main()
