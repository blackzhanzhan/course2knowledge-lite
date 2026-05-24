from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "bilibili-import" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))

from course2knowledge_lite_bilibili import build_bilibili_json_fetcher  # noqa: E402
from course2knowledge_lite_bilibili import fetch_bilibili_timed_subtitles  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_pipeline_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_collection_skeleton_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_lecture_transcript_by_reference_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_lecture_transcript_to_store  # noqa: E402
from course2knowledge_lite_bilibili import import_manual_transcript_by_reference_to_store  # noqa: E402
from course2knowledge_lite_bilibili import probe_lecture_transcript_source_by_reference  # noqa: E402
from course2knowledge_lite_store import SQLiteCourseStore  # noqa: E402
from course2knowledge_lite_store.multimodal import require_ffmpeg  # noqa: E402
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
                {"from": 0.08, "to": 3.32, "content": "RAG retrieves course evidence before answering."},
                {"from": 3.32, "to": 4.5, "content": "An Agent plans tool calls after the evidence is grounded."},
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

    def test_request_scoped_cookie_fetcher_uses_cookie_header_and_redacts_errors(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["cookie"] = request.headers.get("Cookie")
            captured["timeout"] = timeout
            raise RuntimeError("upstream rejected SESSDATA=super-secret-value")

        fetcher = build_bilibili_json_fetcher(cookie="SESSDATA=super-secret-value; bili_jct=csrf-token")
        with patch.object(subtitles_module, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError) as context:
                fetcher("https://api.example/path", {"q": "1"}, "https://ref.example")

        self.assertEqual(captured["cookie"], "SESSDATA=super-secret-value; bili_jct=csrf-token")
        self.assertEqual(captured["timeout"], 30)
        self.assertNotIn("super-secret-value", str(context.exception))
        self.assertNotIn("csrf-token", str(context.exception))
        self.assertIn("[REDACTED_BILIBILI_COOKIE_VALUE]", str(context.exception))
        self.assertTrue(getattr(fetcher, "_bilibili_cookie_present", False))

    def test_fetch_bilibili_timed_subtitles_normalizes_segments(self) -> None:
        bundle = fetch_bilibili_timed_subtitles(
            "https://www.bilibili.com/video/BV00000001",
            fetch_json=fake_bilibili_fetch_json,
        )

        self.assertEqual(bundle.source_id, "BV00000001")
        self.assertEqual(bundle.video_title, "Lecture 1")
        self.assertEqual(len(bundle.timed_lines), 2)
        self.assertEqual(bundle.timed_lines[0]["start_seconds"], 0.08)
        self.assertEqual(bundle.timed_lines[0]["text"], "RAG retrieves course evidence before answering.")

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
            segments = SQLiteCourseStore(temp_dir).read_transcript_segments("course_demo", lecture["lecture_id"])

        self.assertEqual(result["segment_count"], 2)
        self.assertIn("course2knowledge-lite.sqlite3::transcript_segments", result["path"])
        self.assertEqual(segments[0]["segment_id"], "course_demo::lecture::001::seg::00001")
        self.assertEqual(segments[1]["text"], "An Agent plans tool calls after the evidence is grounded.")

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
            segments = SQLiteCourseStore(temp_dir).read_transcript_segments(
                skeleton["course"]["course_id"],
                result["lecture_id"],
            )

        self.assertEqual(result["course_id"], skeleton["course"]["course_id"])
        self.assertEqual(result["import_id"], skeleton["import_status"]["import_id"])
        self.assertEqual(result["lecture"]["sequence"], 1)
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(segments[0]["text"], "RAG retrieves course evidence before answering.")

    def test_import_collection_pipeline_builds_notes_atoms_gates_and_ready_gate(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [
                            {"title": "Lecture 1", "bvid": "BV00000001"},
                            {"title": "Lecture 2", "bvid": "BV00000002"},
                        ],
                        "page": {"total": 2},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
            )
            store = SQLiteCourseStore(temp_dir)
            course_id = result["course"]["course_id"]
            readiness = store.summarize_import_readiness(course_id)
            runs = store.list_import_runs(course_id=course_id)
            events = store.list_import_events(result["run_id"])
            notes = store.list_notes(course_id=course_id)
            cards = store.list_knowledge_cards(course_id=course_id)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(runs[0]["status"], "completed")
        self.assertEqual(runs[0]["stage"], "ready_gate")
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["ready_lecture_count"], 2)
        self.assertEqual(len(notes), 2)
        self.assertGreaterEqual(len(cards), 2)
        self.assertIn("## 总摘要", notes[0]["body"])
        self.assertIn("## 知识原子", notes[0]["body"])
        self.assertIn("## 复习问题", notes[0]["body"])
        self.assertIn("## 证据锚点", notes[0]["body"])
        self.assertNotIn("## Transcript Evidence", notes[0]["body"])
        self.assertTrue(all("你能" in question for card in cards for question in card["review_questions"]))
        self.assertGreater(readiness["total_gate_count"], 0)
        self.assertEqual(events[-1]["event_type"], "ready_gate")

    def test_import_collection_pipeline_limits_skeleton_when_max_lectures_is_set(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [
                            {"title": "Lecture 1", "bvid": "BV00000001"},
                            {"title": "Lecture 2", "bvid": "BV00000002"},
                            {"title": "Lecture 3", "bvid": "BV00000003"},
                        ],
                        "page": {"total": 3},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-20T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
                max_lectures=1,
            )
            store = SQLiteCourseStore(temp_dir)
            course_id = result["course"]["course_id"]
            lectures = store.read_lectures(course_id)
            readiness = store.summarize_import_readiness(course_id)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["lectures"]), 1)
        self.assertEqual(len(lectures), 1)
        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["lecture_count"], 1)
        self.assertEqual(readiness["ready_lecture_count"], 1)

    def test_import_collection_pipeline_defaults_to_model_dossier_generation(self) -> None:
        calls: list[tuple[str, str | None]] = []

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

        def fake_dossier(**kwargs):
            calls.append((kwargs.get("compile_mode"), kwargs.get("compile_provider")))
            from course2knowledge_lite_store.lecture_dossier import LiteLectureDossier

            lecture = dict(kwargs.get("lecture") or {})
            segments = [dict(item) for item in kwargs.get("segments") or []]
            anchor_id = "anc_model_001"
            segment_id = str(segments[0]["segment_id"])
            return LiteLectureDossier(
                course_title="AI interview course",
                lecture_id=str(lecture["lecture_id"]),
                lecture_title="Lecture 1",
                source_url=str(lecture["source_url"]),
                lecture_summary="模型生成的课程主线。",
                sections=[{"heading": "模型主线", "summary": "证据驱动回答", "anchor_ids": [anchor_id]}],
                anchors=[
                    {
                        "anchor_id": anchor_id,
                        "modality": "subtitle",
                        "source_line_ids": [1],
                        "source_segment_ids": [segment_id],
                        "start_timestamp": "00:00:00",
                        "end_timestamp": "00:00:06",
                        "suggested_screenshot_timestamp": "00:00:00",
                        "evidence_quote": "RAG retrieves course evidence before answering.",
                    }
                ],
                atoms=[
                    {
                        "atom_id": "atom_model_001",
                        "canonical_title": "RAG 回答前先检索课程证据",
                        "summary": "先检索证据再组织回答。",
                        "body_markdown": "核心意思：RAG 先检索课程证据，再回答问题。",
                        "atom_type": "procedure",
                        "anchor_ids": [anchor_id],
                        "review_questions": ["为什么 RAG 回答前需要先检索课程证据？"],
                        "confidence": 0.92,
                        "status_lite": "locked",
                    }
                ],
                relations=[],
                review_questions=["为什么 RAG 回答前需要先检索课程证据？"],
                prerequisites=[],
                pitfalls=[],
                minimal_checks=[],
                minimal_examples=[],
                followup_scaffold=[],
                feedback_routes=[],
                search_hooks=[],
                provider="course2knowledge_lite_model_compile",
                compile_source="model_map_reduce",
            )

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "course2knowledge_lite_bilibili.handoff.build_lite_lecture_dossier",
            side_effect=fake_dossier,
        ):
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-20T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
            )
            store = SQLiteCourseStore(temp_dir)
            course_id = result["course"]["course_id"]
            cards = store.list_knowledge_cards(course_id=course_id)
            notes = store.list_notes(course_id=course_id)

        self.assertEqual(len(calls), 1)
        self.assertTrue(all(call == ("model", "deepseek") for call in calls))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(cards[0]["title"], "RAG 回答前先检索课程证据")
        self.assertIn("provider: course2knowledge_lite_model_compile", notes[0]["body"])

    def test_import_collection_pipeline_can_process_lectures_with_worker_pool(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "Parallel course"},
                        "archives": [
                            {"title": "Lecture 1", "bvid": "BV00000001"},
                            {"title": "Lecture 2", "bvid": "BV00000002"},
                            {"title": "Lecture 3", "bvid": "BV00000003"},
                            {"title": "Lecture 4", "bvid": "BV00000004"},
                        ],
                        "page": {"total": 4},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        def slow_fallback_dossier(**kwargs):
            time.sleep(0.05)
            from course2knowledge_lite_store.lecture_dossier import build_lite_lecture_dossier

            return build_lite_lecture_dossier(
                course=kwargs.get("course") or {},
                lecture=kwargs.get("lecture") or {},
                segments=kwargs.get("segments") or [],
                compile_mode="fallback",
                compile_provider=None,
            )

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "course2knowledge_lite_bilibili.handoff.build_lite_lecture_dossier",
            side_effect=slow_fallback_dossier,
        ):
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-20T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
                lecture_workers=2,
            )
            store = SQLiteCourseStore(temp_dir)
            course_id = result["course"]["course_id"]
            readiness = store.summarize_import_readiness(course_id)
            events = store.list_import_events(result["run_id"])
            cards = store.list_knowledge_cards(course_id=course_id)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(readiness["ready_lecture_count"], 4)
        self.assertEqual(len([event for event in events if event["event_type"] == "lecture_completed"]), 4)
        self.assertEqual({card["lecture_id"] for card in cards}, {lecture["lecture_id"] for lecture in result["lectures"]})

    def test_import_pipeline_applies_large_course_parallelism_profile(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "Large course"},
                        "archives": [
                            {"title": f"Lecture {index}", "bvid": f"BV{index:08d}"}
                            for index in range(1, 71)
                        ],
                        "page": {"total": 70},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-20T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
                lecture_workers=10,
                max_chunk_workers=8,
                max_concurrent_requests=80,
            )
            events = SQLiteCourseStore(temp_dir).list_import_events(result["run_id"])

        parallel_event = next(event for event in events if event["event_type"] == "parallelism_resolved")
        self.assertEqual(parallel_event["payload"]["parallelism_profile"]["profile_id"], "large_course")
        self.assertEqual(
            parallel_event["payload"]["effective_parallelism"],
            {
                "lecture_workers": 12,
                "dossier_chunk_workers": 8,
                "dossier_request_concurrency": 8,
            },
        )

    def test_import_pipeline_accepts_bilibili_video_url_as_course_source(self) -> None:
        def fake_video_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/web-interface/view"):
                self.assertEqual(params["bvid"], "BV1b7411N798")
                self.assertIn("BV1b7411N798", referer)
                return {
                    "code": 0,
                    "data": {
                        "aid": 1001,
                        "title": "王道计算机考研 数据结构",
                        "bvid": "BV1b7411N798",
                        "pages": [
                            {"page": 1, "cid": 2001, "part": "0.0 课程白嫖指南"},
                            {"page": 2, "cid": 2002, "part": "1.1 绪论"},
                        ],
                        "ugc_season": {
                            "title": "王道考研408公益课程",
                            "sections": [
                                {
                                    "episodes": [
                                        {
                                            "bvid": "BV_SHOULD_NOT_MIX",
                                            "title": "其他科目",
                                            "pages": [{"page": 1, "cid": 3001, "part": "其他"}],
                                        }
                                    ]
                                }
                            ],
                        },
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_pipeline_to_store(
                "https://www.bilibili.com/video/BV1b7411N798?spm_id_from=333.788.videopod.episodes&p=1",
                store_root=temp_dir,
                now="2026-05-19T16:20:00Z",
                fetch_json=fake_video_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
            )
            store = SQLiteCourseStore(temp_dir)
            lectures = store.read_lectures(result["course"]["course_id"])
            readiness = store.summarize_import_readiness(result["course"]["course_id"])

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["course"]["title"], "王道计算机考研 数据结构")
        self.assertEqual(len(lectures), 2)
        self.assertEqual(lectures[0]["source_url"], "https://www.bilibili.com/video/BV1b7411N798?p=1")
        self.assertEqual(lectures[1]["source_url"], "https://www.bilibili.com/video/BV1b7411N798?p=2")
        self.assertEqual(readiness["ready_lecture_count"], 2)

    def test_import_collection_pipeline_records_visual_keyframes_unavailable_without_media(self) -> None:
        def fake_collection_and_subtitle_fetch(api_url: str, params: dict[str, str], referer: str) -> dict[str, object]:
            if api_url.endswith("/x/polymer/web-space/seasons_archives_list"):
                return {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [
                            {"title": "Lecture 1", "bvid": "BV00000001"},
                            {"title": "Lecture 2", "bvid": "BV00000002"},
                        ],
                        "page": {"total": 2},
                    },
                }
            return fake_bilibili_fetch_json(api_url, params, referer)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                compile_mode="fallback",
                compile_provider=None,
            )
            store = SQLiteCourseStore(temp_dir)
            artifacts = store.list_import_artifacts(run_id=result["run_id"], artifact_type="visual_keyframes")
            visuals = store.list_visual_evidence(course_id=result["course"]["course_id"])

        self.assertEqual(len(artifacts), 2)
        self.assertEqual({artifact["status"] for artifact in artifacts}, {"unavailable"})
        self.assertTrue(all(artifact["payload"]["reason"] == "missing_source_media" for artifact in artifacts))
        self.assertEqual(visuals, [])

    def test_import_collection_pipeline_generates_visual_keyframe_when_media_is_available(self) -> None:
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

        ffmpeg = require_ffmpeg()
        with tempfile.TemporaryDirectory() as temp_dir:
            media_path = Path(temp_dir) / "lecture.mp4"
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=160x90:rate=10:duration=5",
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
            result = import_collection_pipeline_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=fake_collection_and_subtitle_fetch,
                lecture_media_paths={"1": str(media_path)},
                public_repo_root=temp_dir,
                compile_mode="fallback",
                compile_provider=None,
            )
            store = SQLiteCourseStore(temp_dir)
            artifacts = store.list_import_artifacts(run_id=result["run_id"], artifact_type="visual_keyframes")
            visuals = store.list_visual_evidence(course_id=result["course"]["course_id"])

            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0]["status"], "ready")
            self.assertEqual(artifacts[0]["payload"]["provenance"], "generated_keyframe")
            self.assertGreaterEqual(artifacts[0]["payload"]["visual_count"], 1)
            self.assertGreaterEqual(len(visuals), 1)
            self.assertIn("generated_keyframe", visuals[0]["provenance"])
            self.assertTrue((Path(temp_dir) / visuals[0]["image_path"]).exists())

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

    def test_import_manual_transcript_by_reference_writes_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = import_collection_skeleton_to_store(
                "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                store_root=temp_dir,
                now="2026-05-14T00:00:00Z",
                fetch_json=lambda api_url, params, referer: {
                    "code": 0,
                    "data": {
                        "meta": {"name": "AI interview course"},
                        "archives": [{"title": "Lecture 1", "bvid": "BV00000001"}],
                        "page": {"total": 1},
                    },
                },
            )
            result = import_manual_transcript_by_reference_to_store(
                store_root=temp_dir,
                import_id=skeleton["import_status"]["import_id"],
                lecture_sequence=1,
                transcript_text="第一段介绍课程目标。\n第二段说明 RAG 和 Agent 的区别。",
            )
            segments = SQLiteCourseStore(temp_dir).read_transcript_segments(
                skeleton["course"]["course_id"],
                result["lecture_id"],
            )

        self.assertEqual(result["source_type"], "manual_transcript_text")
        self.assertEqual(result["segment_count"], 2)
        self.assertEqual(segments[0]["segment_id"], f"{result['lecture_id']}::manual::00001")
        self.assertEqual(segments[0]["start_seconds"], 0.0)
        self.assertIn("课程目标", segments[0]["text"])
        self.assertIn("RAG", segments[1]["text"])


if __name__ == "__main__":
    unittest.main()
