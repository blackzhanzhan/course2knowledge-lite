from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))

from course2knowledge_lite_bilibili import (  # noqa: E402
    expand_bilibili_collection_url,
    expand_bilibili_source_url,
    expand_bilibili_video_url,
    is_bilibili_collection_url,
    is_bilibili_video_url,
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

    def test_video_url_expands_multi_page_current_video_before_parent_season(self) -> None:
        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            self.assertTrue(api_url.endswith("/x/web-interface/view"))
            self.assertEqual(params["bvid"], "BV1b7411N798")
            self.assertIn("BV1b7411N798", referer)
            return {
                "code": 0,
                "data": {
                    "title": "王道计算机考研 数据结构",
                    "bvid": "BV1b7411N798",
                    "pages": [
                        {"page": 1, "cid": 101, "part": "0.0 课程白嫖指南"},
                        {"page": 2, "cid": 102, "part": "1.1 绪论"},
                    ],
                    "ugc_season": {
                        "title": "王道考研408公益课程",
                        "sections": [
                            {
                                "episodes": [
                                    {
                                        "bvid": "BV-parent",
                                        "title": "不应混入的大系列",
                                        "pages": [{"page": 1, "cid": 201, "part": "父系列第一页"}],
                                    }
                                ]
                            }
                        ],
                    },
                },
            }

        collection = expand_bilibili_video_url(
            "https://www.bilibili.com/video/BV1b7411N798?spm_id_from=333.788.videopod.episodes&p=1",
            fetch_json=fake_fetch_json,
        )

        self.assertTrue(is_bilibili_video_url("https://www.bilibili.com/video/BV1b7411N798?p=2"))
        self.assertFalse(is_bilibili_collection_url("https://www.bilibili.com/video/BV1b7411N798?p=2"))
        self.assertEqual(collection.title, "王道计算机考研 数据结构")
        self.assertEqual(len(collection.videos), 2)
        self.assertEqual(collection.videos[0].title, "0.0 课程白嫖指南")
        self.assertEqual(collection.videos[0].source_url, "https://www.bilibili.com/video/BV1b7411N798?p=1")
        self.assertEqual(collection.videos[1].source_url, "https://www.bilibili.com/video/BV1b7411N798?p=2")
        self.assertNotIn("BV-parent", [video.bvid for video in collection.videos])

    def test_single_page_video_can_expand_ugc_season_episode_pages(self) -> None:
        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            del api_url, referer
            self.assertEqual(params["bvid"], "BVSEASONENTRY")
            return {
                "code": 0,
                "data": {
                    "title": "入口视频",
                    "bvid": "BVSEASONENTRY",
                    "pages": [{"page": 1, "cid": 1, "part": "入口"}],
                    "ugc_season": {
                        "title": "真实系列课",
                        "sections": [
                            {
                                "episodes": [
                                    {
                                        "bvid": "BV00000001",
                                        "title": "第一章",
                                        "pages": [
                                            {"page": 1, "cid": 101, "part": "导论"},
                                            {"page": 2, "cid": 102, "part": "结构"},
                                        ],
                                    },
                                    {
                                        "bvid": "BV00000002",
                                        "title": "第二章",
                                        "page": {"page": 1, "cid": 201, "part": "实践"},
                                    },
                                ]
                            }
                        ],
                    },
                },
            }

        collection = expand_bilibili_source_url(
            "https://www.bilibili.com/video/BVSEASONENTRY",
            fetch_json=fake_fetch_json,
        )

        self.assertEqual(collection.title, "真实系列课")
        self.assertEqual(len(collection.videos), 3)
        self.assertEqual([video.sequence for video in collection.videos], [1, 2, 3])
        self.assertEqual(collection.videos[0].title, "第一章 / 导论")
        self.assertEqual(collection.videos[1].source_url, "https://www.bilibili.com/video/BV00000001?p=2")
        self.assertEqual(collection.videos[2].title, "第二章 / 实践")

    def test_single_video_without_season_expands_to_one_lecture(self) -> None:
        def fake_fetch_json(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            del api_url, referer
            self.assertEqual(params["bvid"], "BVONEVIDEO")
            return {
                "code": 0,
                "data": {
                    "title": "单视频公开课",
                    "bvid": "BVONEVIDEO",
                    "pages": [{"page": 1, "cid": 1001, "part": "完整一讲"}],
                },
            }

        collection = expand_bilibili_source_url("https://www.bilibili.com/video/BVONEVIDEO", fetch_json=fake_fetch_json)

        self.assertEqual(collection.title, "单视频公开课")
        self.assertEqual(len(collection.videos), 1)
        self.assertEqual(collection.videos[0].title, "完整一讲")
        self.assertEqual(collection.videos[0].source_url, "https://www.bilibili.com/video/BVONEVIDEO?p=1")


if __name__ == "__main__":
    unittest.main()
