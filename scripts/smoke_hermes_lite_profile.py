#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


PLUGIN_NAME = "course2knowledge-lite"
EXPECTED_TOOLS = [
    "collection_import_start",
    "import_status_get",
    "lecture_transcript_import",
    "lecture_transcript_import_by_ref",
]


class FakeHermesContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, **kwargs: Any) -> None:
        self.tools[str(kwargs["name"])] = dict(kwargs)


def _load_profile_plugin(profile_root: Path):
    plugin_init = profile_root / "plugins" / PLUGIN_NAME / "__init__.py"
    if not plugin_init.exists():
        raise RuntimeError(f"Course2Knowledge Lite plugin is missing: {plugin_init}")
    module_name = "course2knowledge_lite_profile_smoke_plugin"
    spec = importlib.util.spec_from_file_location(module_name, plugin_init)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load plugin module: {plugin_init}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def smoke_profile(profile_root: str | Path) -> dict[str, Any]:
    root = Path(profile_root).expanduser().resolve()
    module = _load_profile_plugin(root)
    ctx = FakeHermesContext()
    module.register(ctx)
    registered_tools = sorted(ctx.tools)
    if registered_tools != sorted(EXPECTED_TOOLS):
        raise RuntimeError(f"Unexpected registered tools: {registered_tools}")

    from course2knowledge_lite_store import JsonCourseStore, build_course_skeleton

    with tempfile.TemporaryDirectory() as temp_dir:
        skeleton = build_course_skeleton(
            title="Smoke course",
            source_url="https://space.bilibili.com/1112988584/lists/7726472?type=season",
            video_refs=[
                {
                    "sequence": 1,
                    "bvid": "BV00000001",
                    "title": "Smoke lecture",
                    "source_url": "https://www.bilibili.com/video/BV00000001",
                }
            ],
            now="2026-05-14T00:00:00Z",
        )
        JsonCourseStore(temp_dir).write_skeleton(skeleton)
        raw = ctx.tools["import_status_get"]["handler"](
            {"store_root": temp_dir, "import_id": skeleton.import_status.import_id}
        )
        sample_payload = json.loads(raw)

    return {
        "status": "passed",
        "profile_root": str(root),
        "toolset": PLUGIN_NAME,
        "registered_tools": registered_tools,
        "sample_tool": "import_status_get",
        "sample_tool_status": sample_payload.get("status"),
        "sample_import_stage": (sample_payload.get("import_status") or {}).get("stage"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test a synced Course2Knowledge Lite Hermes profile.")
    parser.add_argument("--profile-root", required=True)
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = smoke_profile(args.profile_root)
    if str(args.output or "").strip():
        output_path = Path(str(args.output)).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
