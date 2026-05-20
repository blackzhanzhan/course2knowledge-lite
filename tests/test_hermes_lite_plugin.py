from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "hermes" / "plugins" / "course2knowledge-lite"
sys.path.insert(0, str(ROOT / "packages" / "course-store" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "guidance" / "src"))

from course2knowledge_lite_store import (  # noqa: E402
    SQLiteCourseStore,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    build_course_skeleton,
)


class FakeHermesContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, object]] = {}

    def register_tool(self, **kwargs) -> None:
        self.tools[str(kwargs["name"])] = dict(kwargs)


def load_plugin_module():
    module_name = "course2knowledge_lite_hermes_plugin"
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_ROOT / "__init__.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Hermes Lite plugin module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def manifest_tool_names() -> list[str]:
    lines = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines()
    names: list[str] = []
    in_tools = False
    for line in lines:
        stripped = line.strip()
        if stripped == "provides_tools:":
            in_tools = True
            continue
        if in_tools and stripped.startswith("- "):
            names.append(stripped[2:].strip())
    return names


class HermesLitePluginTests(unittest.TestCase):
    def test_plugin_registers_manifest_tools(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()

        module.register(ctx)

        self.assertEqual(sorted(ctx.tools), sorted(manifest_tool_names()))
        for tool_name, payload in ctx.tools.items():
            self.assertEqual(payload["toolset"], "course2knowledge-lite")
            self.assertIn("handler", payload)
            self.assertEqual(payload["schema"]["name"], tool_name)

    def test_learner_tools_allow_omitting_course_id_when_course_is_current(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()

        module.register(ctx)

        learner_tools = [
            "course_transcript_coverage_get",
            "knowledge_cards_generate",
            "knowledge_card_list",
            "knowledge_card_get",
            "course_visual_evidence_send",
            "learning_guide_get",
            "lecture_reader_get",
            "course_search",
            "course_question_answer",
            "note_create",
            "note_list",
            "note_update",
            "note_delete",
            "bookmark_create",
            "bookmark_list",
            "bookmark_delete",
            "reading_progress_set",
            "reading_progress_get",
        ]
        for tool_name in learner_tools:
            parameters = ctx.tools[tool_name]["schema"]["parameters"]
            self.assertNotIn("course_id", parameters.get("required", []), tool_name)

    def test_import_status_tool_reads_local_store(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
            skeleton = build_course_skeleton(
                title="AI interview course",
                source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
                video_refs=[
                    {
                        "sequence": 1,
                        "bvid": "BV00000001",
                        "title": "Lecture 1",
                        "source_url": "https://www.bilibili.com/video/BV00000001",
                    }
                ],
                now="2026-05-14T00:00:00Z",
            )
            SQLiteCourseStore(temp_dir).write_skeleton(skeleton)
            raw = ctx.tools["import_status_get"]["handler"](
                {"store_root": temp_dir, "import_id": skeleton.import_status.import_id}
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "import_status_get")
        self.assertEqual(payload["import_status"]["stage"], "collection_expanded")

    def test_collection_import_tool_calls_package_api(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)
        tools_module = sys.modules[f"{module.__name__}.tools"]

        def fake_import_collection(source_url, *, store_root):
            return {
                "course": {"course_id": "course_demo", "source_url": source_url},
                "lectures": [],
                "import_status": {"import_id": "import_course_demo", "status": "accepted"},
                "paths": {"store_root": str(store_root)},
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            tools_module,
            "import_collection_skeleton_to_store",
            side_effect=fake_import_collection,
        ):
            raw = ctx.tools["collection_import_start"]["handler"](
                {
                    "source_url": "https://space.bilibili.com/1112988584/lists/7726472?type=season",
                    "store_root": temp_dir,
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["course"]["course_id"], "course_demo")
        self.assertTrue(payload["paths"]["store_root"])

    def test_lecture_transcript_tool_calls_package_api(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)
        tools_module = sys.modules[f"{module.__name__}.tools"]

        def fake_import_transcript(*, store_root, course_id, lecture):
            return {
                "lecture_id": lecture["lecture_id"],
                "source_id": lecture["source_id"],
                "segment_count": 2,
                "path": str(Path(store_root) / "segments.json"),
                "course_id": course_id,
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            tools_module,
            "import_lecture_transcript_to_store",
            side_effect=fake_import_transcript,
        ):
            raw = ctx.tools["lecture_transcript_import"]["handler"](
                {
                    "store_root": temp_dir,
                    "course_id": "course_demo",
                    "lecture": {
                        "lecture_id": "course_demo::lecture::001",
                        "source_id": "BV00000001",
                        "source_url": "https://www.bilibili.com/video/BV00000001",
                    },
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["segment_count"], 2)
        self.assertEqual(payload["source_id"], "BV00000001")

    def test_lecture_transcript_by_ref_tool_calls_package_api(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)
        tools_module = sys.modules[f"{module.__name__}.tools"]

        def fake_import_transcript_by_ref(*, store_root, course_id, import_id, lecture_sequence, lecture_id, source_id):
            return {
                "course_id": course_id,
                "import_id": import_id,
                "lecture_id": lecture_id or "course_demo::lecture::001",
                "source_id": source_id or "BV00000001",
                "segment_count": 2,
                "path": str(Path(store_root) / "segments.json"),
                "lecture": {"sequence": int(lecture_sequence), "title": "Lecture 1"},
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            tools_module,
            "import_lecture_transcript_by_reference_to_store",
            side_effect=fake_import_transcript_by_ref,
        ):
            raw = ctx.tools["lecture_transcript_import_by_ref"]["handler"](
                {
                    "store_root": temp_dir,
                    "import_id": "import_course_demo",
                    "course_id": "course_demo",
                    "lecture_sequence": 1,
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "lecture_transcript_import_by_ref")
        self.assertEqual(payload["segment_count"], 2)
        self.assertEqual(payload["lecture"]["sequence"], 1)

    def test_lecture_transcript_source_probe_tool_calls_package_api(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)
        tools_module = sys.modules[f"{module.__name__}.tools"]

        def fake_probe(*, store_root, course_id, import_id, lecture_sequence, lecture_id, source_id):
            return {
                "course_id": course_id,
                "import_id": import_id,
                "lecture": {"sequence": int(lecture_sequence), "lecture_id": lecture_id or "course_demo::lecture::001"},
                "subtitle_source": {"available": False, "cookie_present": False},
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            tools_module,
            "probe_lecture_transcript_source_by_reference",
            side_effect=fake_probe,
        ):
            raw = ctx.tools["lecture_transcript_source_probe"]["handler"](
                {
                    "store_root": temp_dir,
                    "import_id": "import_course_demo",
                    "course_id": "course_demo",
                    "lecture_sequence": 1,
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "lecture_transcript_source_probe")
        self.assertFalse(payload["subtitle_source"]["available"])
        self.assertFalse(payload["subtitle_source"]["cookie_present"])

    def test_manual_transcript_import_tool_calls_package_api(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)
        tools_module = sys.modules[f"{module.__name__}.tools"]

        def fake_manual_import(*, store_root, transcript_text, course_id, import_id, lecture_sequence, lecture_id, source_id):
            return {
                "course_id": course_id,
                "import_id": import_id,
                "lecture_id": lecture_id or "course_demo::lecture::001",
                "source_id": source_id or "BV00000001",
                "segment_count": 2,
                "path": str(Path(store_root) / "manual.segments.json"),
                "source_type": "manual_transcript_text",
                "lecture": {"sequence": int(lecture_sequence), "title": "Lecture 1"},
                "text_len": len(transcript_text),
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            tools_module,
            "import_manual_transcript_by_reference_to_store",
            side_effect=fake_manual_import,
        ):
            raw = ctx.tools["manual_transcript_import"]["handler"](
                {
                    "store_root": temp_dir,
                    "import_id": "import_course_demo",
                    "course_id": "course_demo",
                    "lecture_sequence": 1,
                    "transcript_text": "hello\nworld",
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "manual_transcript_import")
        self.assertEqual(payload["source_type"], "manual_transcript_text")
        self.assertEqual(payload["segment_count"], 2)

    def test_reader_search_and_qa_tools_use_transcript_segments(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
                        text="RAG retrieves course evidence, while an Agent plans actions and calls tools.",
                    )
                ],
            )
            common_args = {"store_root": temp_dir, "course_id": skeleton.course.course_id}
            coverage_raw = ctx.tools["course_transcript_coverage_get"]["handler"](common_args)
            reader_raw = ctx.tools["lecture_reader_get"]["handler"]({**common_args, "lecture_sequence": 1})
            search_raw = ctx.tools["course_search"]["handler"]({**common_args, "query": "RAG Agent"})
            qa_raw = ctx.tools["course_question_answer"]["handler"](
                {**common_args, "question": "RAG 和 Agent 的区别是什么？"}
            )
            auto_search_raw = ctx.tools["course_search"]["handler"]({"store_root": temp_dir, "query": "RAG Agent"})
            auto_qa_raw = ctx.tools["course_question_answer"]["handler"](
                {"store_root": temp_dir, "question": "What is the difference between RAG and Agent?"}
            )
            persisted_threads = SQLiteCourseStore(temp_dir).list_chat_threads(
                course_id=skeleton.course.course_id,
                channel="hermes",
            )

        coverage_payload = json.loads(coverage_raw)
        reader_payload = json.loads(reader_raw)
        search_payload = json.loads(search_raw)
        qa_payload = json.loads(qa_raw)
        auto_search_payload = json.loads(auto_search_raw)
        auto_qa_payload = json.loads(auto_qa_raw)
        self.assertEqual(coverage_payload["status"], "completed")
        self.assertEqual(coverage_payload["coverage"]["covered_lecture_count"], 1)
        self.assertEqual(reader_payload["status"], "completed")
        self.assertTrue(reader_payload["reader"]["has_transcript"])
        self.assertEqual(search_payload["result_count"], 1)
        self.assertEqual(qa_payload["answer"]["status"], "answered")
        self.assertEqual(qa_payload["answer"]["citation_count"], 1)
        self.assertEqual(auto_search_payload["status"], "completed")
        self.assertEqual(auto_search_payload["result_count"], 1)
        self.assertEqual(auto_qa_payload["status"], "completed")
        self.assertEqual(auto_qa_payload["answer"]["status"], "answered")
        self.assertEqual(qa_payload["answer"]["chat_turn"]["route"], "search")
        self.assertIn("message_delta", [event["event_type"] for event in qa_payload["answer"]["chat_turn"]["events"]])
        self.assertEqual(len(persisted_threads), 2)

    def test_auto_course_selection_reports_human_ambiguity_for_multiple_courses(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SQLiteCourseStore(temp_dir)
            for course_id, title in [("course_one", "First course"), ("course_two", "Second course")]:
                skeleton = build_course_skeleton(
                    course_id=course_id,
                    title=title,
                    source_url=f"https://example.com/{course_id}",
                    video_refs=[
                        {
                            "sequence": 1,
                            "bvid": f"BV{course_id}",
                            "title": "Lecture 1",
                            "source_url": f"https://www.bilibili.com/video/BV{course_id}",
                        }
                    ],
                    now="2026-05-14T00:00:00Z",
                )
                store.write_skeleton(skeleton)

            raw = ctx.tools["course_question_answer"]["handler"](
                {"store_root": temp_dir, "question": "What did I just learn?"}
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("multiple imported courses", payload["error"])
        self.assertIn("First course", payload["error"])
        self.assertIn("Second course", payload["error"])
        self.assertNotIn("course_id", payload["error"])

    def test_learning_state_tools_use_local_course_store(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
            segment_id = f"{lecture.lecture_id}::manual::00001"
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
            common_args = {
                "store_root": temp_dir,
                "course_id": skeleton.course.course_id,
                "lecture_sequence": 1,
            }

            note_raw = ctx.tools["note_create"]["handler"]({**common_args, "body": "RAG uses evidence."})
            note_list_raw = ctx.tools["note_list"]["handler"](
                {"store_root": temp_dir, "course_id": skeleton.course.course_id}
            )
            bookmark_raw = ctx.tools["bookmark_create"]["handler"](
                {
                    "store_root": temp_dir,
                    "course_id": skeleton.course.course_id,
                    "target_type": "segment",
                    "target_id": segment_id,
                }
            )
            progress_raw = ctx.tools["reading_progress_set"]["handler"]({**common_args, "status": "read"})
            invalid_progress_raw = ctx.tools["reading_progress_set"]["handler"]({**common_args, "status": "mastered"})

        note_payload = json.loads(note_raw)
        note_list_payload = json.loads(note_list_raw)
        bookmark_payload = json.loads(bookmark_raw)
        progress_payload = json.loads(progress_raw)
        invalid_progress_payload = json.loads(invalid_progress_raw)
        self.assertEqual(note_payload["status"], "completed")
        self.assertEqual(note_list_payload["note_count"], 1)
        self.assertEqual(bookmark_payload["bookmark"]["target_id"], segment_id)
        self.assertEqual(progress_payload["progress"]["status"], "read")
        self.assertEqual(invalid_progress_payload["status"], "failed")
        self.assertEqual(invalid_progress_payload["tool"], "reading_progress_set")

    def test_learning_guide_tool_returns_read_only_guidance(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
                        text="RAG retrieves course evidence before an Agent plans tool calls.",
                    )
                ],
            )
            store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )
            progress_before = store.list_reading_progress(course_id=skeleton.course.course_id)
            raw = ctx.tools["learning_guide_get"]["handler"](
                {
                    "store_root": temp_dir,
                    "course_id": skeleton.course.course_id,
                    "mode": "self_check",
                    "lecture_sequence": 1,
                }
            )
            progress_after = store.list_reading_progress(course_id=skeleton.course.course_id)

        payload = json.loads(raw)
        guide = payload["guide"]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "learning_guide_get")
        self.assertEqual(guide["status"], "completed")
        self.assertEqual(guide["mode"], "self_check")
        self.assertEqual(guide["question_count"], 1)
        self.assertFalse(guide["limits"]["writes_progress"])
        self.assertFalse(guide["limits"]["creates_study_plan"])
        self.assertFalse(guide["limits"]["scores_learner"])
        self.assertEqual(progress_after, progress_before)

    def test_knowledge_card_tools_use_local_transcript_segments(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
            segment_id = f"{lecture.lecture_id}::manual::00001"
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves course evidence before an Agent plans tool calls.",
                    )
                ],
            )
            common_args = {"store_root": temp_dir, "course_id": skeleton.course.course_id}

            generated_raw = ctx.tools["knowledge_cards_generate"]["handler"](common_args)
            listed_raw = ctx.tools["knowledge_card_list"]["handler"](common_args)
            listed_payload = json.loads(listed_raw)
            card_id = listed_payload["cards"][0]["card_id"]
            read_raw = ctx.tools["knowledge_card_get"]["handler"]({**common_args, "card_id": card_id})
            bookmark_raw = ctx.tools["bookmark_create"]["handler"](
                {
                    **common_args,
                    "target_type": "card",
                    "target_id": card_id,
                }
            )

        generated_payload = json.loads(generated_raw)
        read_payload = json.loads(read_raw)
        bookmark_payload = json.loads(bookmark_raw)
        self.assertEqual(generated_payload["status"], "completed")
        self.assertEqual(generated_payload["generated_card_count"], 1)
        self.assertEqual(listed_payload["card_count"], 1)
        self.assertEqual(read_payload["card"]["source_segment_ids"], [segment_id])
        self.assertEqual(bookmark_payload["bookmark"]["target_type"], "card")
        self.assertEqual(bookmark_payload["bookmark"]["target_id"], card_id)

    def test_visual_evidence_tool_returns_explanation_and_single_media_directive(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
            segment_id = f"{lecture.lecture_id}::manual::00001"
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves course evidence before an Agent plans tool calls.",
                    )
                ],
            )
            card = store.generate_knowledge_cards(
                skeleton.course.course_id,
                compile_mode="fallback",
                compile_provider=None,
            )["cards"][0]
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
                        explanation="RAG grounds answers in evidence; Agent plans tool-backed actions.",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="public demo diagram derived from transcript segment",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            raw = ctx.tools["course_visual_evidence_send"]["handler"](
                {
                    "store_root": temp_dir,
                    "query": "Agent 怎么和工具、知识库配合",
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["tool"], "course_visual_evidence_send")
        self.assertEqual(payload["visual_evidence"]["visual_id"], "visual_rag_agent_flow")
        self.assertEqual(payload["chat_turn"]["route"], "visual_evidence")
        self.assertIn("media", [event["event_type"] for event in payload["chat_turn"]["events"]])
        self.assertIn("RAG grounds answers", payload["gateway_reply"])
        self.assertEqual(payload["gateway_reply"].count("MEDIA:"), 1)
        self.assertTrue(Path(payload["media_path"]).exists())

    def test_visual_evidence_tool_prefers_generated_keyframe_for_lecture_request(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
            segment_id = f"{lecture.lecture_id}::manual::00001"
            store.write_transcript_segments(
                skeleton.course.course_id,
                lecture.lecture_id,
                [
                    TranscriptSegmentRecord(
                        segment_id=segment_id,
                        lecture_id=lecture.lecture_id,
                        start_seconds=0.0,
                        end_seconds=6.0,
                        text="RAG retrieves course evidence before an Agent plans tool calls.",
                    )
                ],
            )
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_demo",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id="",
                        title="Demo visual",
                        explanation="demo",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="demo_visual",
                        created_at="2026-05-15T00:00:00Z",
                    ),
                    VisualEvidenceRecord(
                        visual_id="keyframe_generated",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id=segment_id,
                        card_id="",
                        title="关键截图 1",
                        explanation="真实关键帧说明",
                        image_path="docs/assets/visual-evidence/rag-quality-loop.png",
                        source_url=lecture.source_url,
                        provenance="generated_keyframe anchor=anc_test",
                        created_at="2026-05-15T00:00:00Z",
                    ),
                ],
            )
            raw = ctx.tools["course_visual_evidence_send"]["handler"](
                {
                    "store_root": temp_dir,
                    "lecture_id": lecture.lecture_id,
                    "query": "关键截图",
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["visual_evidence"]["visual_id"], "keyframe_generated")
        self.assertIn("generated_keyframe", payload["visual_evidence"]["provenance"])
        self.assertEqual(payload["gateway_reply"].count("MEDIA:"), 1)

    def test_visual_evidence_tool_blocks_demo_visual_for_lecture_key_screenshot_request(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        with tempfile.TemporaryDirectory() as temp_dir:
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
            store.write_visual_evidence_records(
                skeleton.course.course_id,
                [
                    VisualEvidenceRecord(
                        visual_id="visual_demo",
                        course_id=skeleton.course.course_id,
                        lecture_id=lecture.lecture_id,
                        segment_id="",
                        card_id="",
                        title="Demo visual",
                        explanation="demo",
                        image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                        source_url=lecture.source_url,
                        provenance="demo_visual",
                        created_at="2026-05-15T00:00:00Z",
                    )
                ],
            )
            raw = ctx.tools["course_visual_evidence_send"]["handler"](
                {
                    "store_root": temp_dir,
                    "lecture_id": lecture.lecture_id,
                    "query": "关键截图",
                }
            )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("generated keyframe", payload["error"])
        self.assertIn("demo visuals cannot be sent as course screenshots", payload["error"])

    def test_visual_evidence_tool_rejects_raw_image_path_argument(self) -> None:
        module = load_plugin_module()
        ctx = FakeHermesContext()
        module.register(ctx)

        raw = ctx.tools["course_visual_evidence_send"]["handler"](
            {
                "course_id": "course_demo",
                "image_path": "docs/assets/visual-evidence/rag-agent-flow.png",
            }
        )

        payload = json.loads(raw)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["tool"], "course_visual_evidence_send")
        self.assertIn("image_path is not accepted", payload["error"])


if __name__ == "__main__":
    unittest.main()
