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

from course2knowledge_lite_store import JsonCourseStore, build_course_skeleton  # noqa: E402


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
            JsonCourseStore(temp_dir).write_skeleton(skeleton)
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


if __name__ == "__main__":
    unittest.main()
