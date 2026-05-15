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
    "course_transcript_coverage_get",
    "course_question_answer",
    "course_search",
    "import_status_get",
    "knowledge_card_get",
    "knowledge_card_list",
    "knowledge_cards_generate",
    "course_visual_evidence_send",
    "lecture_reader_get",
    "lecture_transcript_import",
    "lecture_transcript_import_by_ref",
    "lecture_transcript_source_probe",
    "manual_transcript_import",
    "note_create",
    "note_delete",
    "note_list",
    "note_update",
    "bookmark_create",
    "bookmark_delete",
    "bookmark_list",
    "reading_progress_get",
    "reading_progress_set",
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

    from course2knowledge_lite_store import (
        JsonCourseStore,
        TranscriptSegmentRecord,
        VisualEvidenceRecord,
        build_course_skeleton,
    )

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
        store = JsonCourseStore(temp_dir)
        store.write_skeleton(skeleton)
        store.write_transcript_segments(
            skeleton.course.course_id,
            skeleton.lectures[0].lecture_id,
            [
                TranscriptSegmentRecord(
                    segment_id=f"{skeleton.lectures[0].lecture_id}::manual::00001",
                    lecture_id=skeleton.lectures[0].lecture_id,
                    start_seconds=0.0,
                    end_seconds=6.0,
                    text="RAG retrieves evidence while an Agent plans tool-using actions.",
                )
            ],
        )
        raw = ctx.tools["import_status_get"]["handler"](
            {"store_root": temp_dir, "import_id": skeleton.import_status.import_id}
        )
        sample_payload = json.loads(raw)
        qa_raw = ctx.tools["course_question_answer"]["handler"](
            {
                "store_root": temp_dir,
                "course_id": skeleton.course.course_id,
                "question": "RAG 和 Agent 的区别是什么？",
            }
        )
        qa_payload = json.loads(qa_raw)
        cards_raw = ctx.tools["knowledge_cards_generate"]["handler"](
            {"store_root": temp_dir, "course_id": skeleton.course.course_id}
        )
        cards_payload = json.loads(cards_raw)
        card_id = cards_payload["cards"][0]["card_id"]
        store.write_visual_evidence_records(
            skeleton.course.course_id,
            [
                VisualEvidenceRecord(
                    visual_id="visual_smoke_rag_agent",
                    course_id=skeleton.course.course_id,
                    lecture_id=skeleton.lectures[0].lecture_id,
                    segment_id=f"{skeleton.lectures[0].lecture_id}::manual::00001",
                    card_id=card_id,
                    title="Smoke RAG and Agent flow",
                    explanation="RAG retrieves evidence while an Agent plans tool-using actions.",
                    image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                    source_url=skeleton.lectures[0].source_url,
                    provenance="public profile smoke fixture",
                    created_at="2026-05-15T00:00:00Z",
                )
            ],
        )
        visual_raw = ctx.tools["course_visual_evidence_send"]["handler"](
            {
                "store_root": temp_dir,
                "course_id": skeleton.course.course_id,
                "query": "Agent",
            }
        )
        visual_payload = json.loads(visual_raw)
        common_args = {
            "store_root": temp_dir,
            "course_id": skeleton.course.course_id,
            "lecture_sequence": 1,
        }
        note_raw = ctx.tools["note_create"]["handler"]({**common_args, "body": "Remember RAG evidence."})
        note_payload = json.loads(note_raw)
        progress_raw = ctx.tools["reading_progress_set"]["handler"]({**common_args, "status": "read"})
        progress_payload = json.loads(progress_raw)

    return {
        "status": "passed",
        "profile_root": str(root),
        "toolset": PLUGIN_NAME,
        "registered_tools": registered_tools,
        "sample_tool": "import_status_get",
        "sample_tool_status": sample_payload.get("status"),
        "sample_import_stage": (sample_payload.get("import_status") or {}).get("stage"),
        "sample_qa_status": (qa_payload.get("answer") or {}).get("status"),
        "sample_qa_citation_count": (qa_payload.get("answer") or {}).get("citation_count"),
        "sample_card_count": cards_payload.get("card_count"),
        "sample_generated_card_count": cards_payload.get("generated_card_count"),
        "sample_visual_status": visual_payload.get("status"),
        "sample_visual_media_count": str(visual_payload.get("gateway_reply") or "").count("MEDIA:"),
        "sample_note_status": note_payload.get("status"),
        "sample_note_body": (note_payload.get("note") or {}).get("body"),
        "sample_progress_status": (progress_payload.get("progress") or {}).get("status"),
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
