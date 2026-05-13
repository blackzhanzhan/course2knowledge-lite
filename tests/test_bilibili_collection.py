from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))

from course2knowledge_lite_bilibili import (  # noqa: E402
    expand_bilibili_collection_url,
    is_bilibili_collection_url,
    parse_bilibili_collection_url,
)


SAMPLE_URL = "https://space.bilibili.com/1112988584/lists/7726472?type=season"


class BilibiliCollectionTests(unittest.TestCase):
    def test_lists_url_parses_mid_and_season_id(self) -> None:
        parsed = parse_bilibili_collection_url(SAMPLE_URL)

        self.assertEqual(parsed.mid, "1112988584")
        self.assertEqual(parsed.season_id, "7726472")
        self.assertTrue(is_bilibili_collection_url(SAMPLE_URL))

    def test_collection_expands_to_ordered_video_refs(self) -> None:
        calls: list[dict[str, str]] = []

        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            del api_url, referer
            calls.append(dict(params))
            return {
                "code": 0,
                "data": {
                    "meta": {"name": "合集·AI大模型面试-全套合集"},
                    "archives": [
                        {"bvid": f"BV{i:08d}", "title": f"Lecture {i}"}
                        for i in range(1, 31)
                    ],
                    "page": {"total": 30},
                },
            }

        collection = expand_bilibili_collection_url(SAMPLE_URL, fetch_json=fake_fetch_json)

        self.assertEqual(collection.title, "合集·AI大模型面试-全套合集")
        self.assertEqual(len(collection.videos), 30)
        self.assertEqual(collection.videos[0].sequence, 1)
        self.assertEqual(collection.videos[0].bvid, "BV00000001")
        self.assertEqual(collection.videos[-1].sequence, 30)
        self.assertEqual(collection.videos[-1].source_url, "https://www.bilibili.com/video/BV00000030")
        self.assertEqual(calls[0]["mid"], "1112988584")
        self.assertEqual(calls[0]["season_id"], "7726472")


if __name__ == "__main__":
    unittest.main()
