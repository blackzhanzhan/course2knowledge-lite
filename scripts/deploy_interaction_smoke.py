#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import request


COLLECTION_URL = "https://space.bilibili.com/1112988584/lists/7726472?type=season"
COURSE_ID = "course_public_deep_learning_demo"
COURSE_TITLE = "Deep Learning Course Demo"
FIXED_NOW = "2026-05-16T00:00:00Z"


class FakeHermesContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, **kwargs: Any) -> None:
        self.tools[str(kwargs["name"])] = dict(kwargs)


def run_interaction_smoke(
    *,
    repo_root: str | Path,
    store_root: str | Path,
    profile_root: str | Path,
    output: str | Path = "",
    port: int = 3191,
) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve()
    store_path = Path(store_root).expanduser().resolve()
    profile_path = Path(profile_root).expanduser().resolve()
    _bootstrap_paths(repo)

    from course2knowledge_lite_store import (
        JsonCourseStore,
        TranscriptSegmentRecord,
        VisualEvidenceRecord,
        build_course_skeleton,
    )

    store = JsonCourseStore(store_path)
    skeleton = _seed_public_course(store)
    course_id = skeleton.course.course_id
    lectures = skeleton.lectures

    coverage = store.summarize_transcript_coverage(course_id)
    cards = store.generate_knowledge_cards(course_id)
    first_card = cards["cards"][0]
    store.write_visual_evidence_records(
        course_id,
        [
            VisualEvidenceRecord(
                visual_id="visual_agent_flow",
                course_id=course_id,
                lecture_id=lectures[0].lecture_id,
                segment_id=f"{lectures[0].lecture_id}::manual::00001",
                card_id=str(first_card["card_id"]),
                title="RAG agent flow",
                explanation="The diagram ties retrieval, evidence, and tool-using action into one learning loop.",
                image_path="docs/assets/visual-evidence/rag-agent-flow.png",
                source_url=lectures[0].source_url,
                provenance="public deploy interaction smoke",
                created_at=FIXED_NOW,
            ),
            VisualEvidenceRecord(
                visual_id="visual_quality_loop",
                course_id=course_id,
                lecture_id=lectures[1].lecture_id,
                segment_id=f"{lectures[1].lecture_id}::manual::00001",
                card_id=str(first_card["card_id"]),
                title="Quality loop",
                explanation="The loop shows how retrieval quality improves when evidence is checked against user intent.",
                image_path="docs/assets/visual-evidence/rag-quality-loop.png",
                source_url=lectures[1].source_url,
                provenance="public deploy interaction smoke",
                created_at=FIXED_NOW,
            ),
        ],
    )

    reader = store.read_lecture_reader(course_id, lecture_sequence=1)
    search_hits = store.search_transcripts(course_id, "RAG Agent", limit=5)
    note = store.create_note(
        course_id,
        lectures[0].lecture_id,
        "RAG is the evidence layer; Agent is the action layer.",
        note_id="note_deploy_interaction",
        now=FIXED_NOW,
    )
    bookmark = store.create_bookmark(
        course_id,
        "card",
        str(first_card["card_id"]),
        bookmark_id="bookmark_deploy_interaction",
        now=FIXED_NOW,
    )
    progress = store.set_reading_progress(
        course_id,
        lectures[0].lecture_id,
        "read",
        now=FIXED_NOW,
    )

    hermes = _run_hermes_path(profile_path, store_path, course_id)
    web = _run_web_path(repo, store_path, course_id, port=port)

    report: dict[str, Any] = {
        "status": "passed",
        "repo_root": str(repo),
        "store_root": str(store_path),
        "profile_root": str(profile_path),
        "course": skeleton.course.to_dict(),
        "lecture_count": len(lectures),
        "coverage": {
            "covered_lecture_count": coverage["covered_lecture_count"],
            "lecture_count": coverage["lecture_count"],
            "total_segment_count": coverage["total_segment_count"],
            "coverage_ratio": coverage["coverage_ratio"],
        },
        "reader": {
            "lecture_title": reader["lecture"]["title"],
            "segment_count": len(reader["segments"]),
        },
        "search": {
            "query": "RAG Agent",
            "result_count": len(search_hits),
            "top_lecture_title": _hit_lecture_title(search_hits[0]) if search_hits else "",
        },
        "cards": {
            "card_count": cards["card_count"],
            "generated_card_count": cards["generated_card_count"],
        },
        "workspace": {
            "note_status": "completed" if note.get("note_id") else "failed",
            "bookmark_status": "completed" if bookmark.get("bookmark_id") else "failed",
            "progress_status": progress.get("status"),
        },
        "hermes": hermes,
        "web": web,
    }
    _assert_report(report)
    if output:
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _bootstrap_paths(repo: Path) -> None:
    roots = [
        repo / "packages" / "bilibili-import" / "src",
        repo / "packages" / "course-store" / "src",
        repo / "packages" / "qa" / "src",
        repo / "packages" / "guidance" / "src",
    ]
    for root in roots:
        text = str(root)
        if text not in sys.path:
            sys.path.insert(0, text)


def _seed_public_course(store: Any) -> Any:
    from course2knowledge_lite_store import TranscriptSegmentRecord, build_course_skeleton

    skeleton = build_course_skeleton(
        course_id=COURSE_ID,
        title=COURSE_TITLE,
        source_url=COLLECTION_URL,
        video_refs=[
            {
                "sequence": 1,
                "bvid": "BV1DEMO001",
                "title": "RAG and Agent",
                "source_url": "https://www.bilibili.com/video/BV1DEMO001",
            },
            {
                "sequence": 2,
                "bvid": "BV1DEMO002",
                "title": "Embedding and Retrieval",
                "source_url": "https://www.bilibili.com/video/BV1DEMO002",
            },
            {
                "sequence": 3,
                "bvid": "BV1DEMO003",
                "title": "Evaluation and Quality Loop",
                "source_url": "https://www.bilibili.com/video/BV1DEMO003",
            },
        ],
        now=FIXED_NOW,
    )
    store.write_skeleton(skeleton)
    transcript_texts = [
        [
            "RAG retrieves course evidence before an Agent decides which tool or action to use.",
            "The learner should ask concrete questions so the answer can cite the right transcript segment.",
        ],
        [
            "Embeddings turn lecture text into searchable vectors, while retrieval brings back the most relevant evidence.",
            "A knowledge base is useful when search, reading, and Q&A all point to the same cited material.",
        ],
        [
            "Evaluation checks whether the answer follows the evidence and whether the user can continue learning.",
            "The quality loop improves when notes, bookmarks, and reading progress preserve what the learner discovered.",
        ],
    ]
    for lecture, texts in zip(skeleton.lectures, transcript_texts, strict=True):
        segments = [
            TranscriptSegmentRecord(
                segment_id=f"{lecture.lecture_id}::manual::{index:05d}",
                lecture_id=lecture.lecture_id,
                start_seconds=float((index - 1) * 12),
                end_seconds=float(index * 12),
                text=text,
            )
            for index, text in enumerate(texts, start=1)
        ]
        store.write_transcript_segments(skeleton.course.course_id, lecture.lecture_id, segments)
    return skeleton


def _run_hermes_path(profile_root: Path, store_root: Path, course_id: str) -> dict[str, Any]:
    plugin_init = profile_root / "plugins" / "course2knowledge-lite" / "__init__.py"
    if not plugin_init.exists():
        raise RuntimeError(f"Hermes Lite plugin is missing: {plugin_init}")
    spec = importlib.util.spec_from_file_location("course2knowledge_lite_interaction_plugin", plugin_init)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Hermes plugin: {plugin_init}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["course2knowledge_lite_interaction_plugin"] = module
    spec.loader.exec_module(module)
    ctx = FakeHermesContext()
    module.register(ctx)
    args = {"store_root": str(store_root), "course_id": course_id}

    coverage = _tool_json(ctx, "course_transcript_coverage_get", args)
    reader = _tool_json(ctx, "lecture_reader_get", {**args, "lecture_sequence": 1})
    search = _tool_json(ctx, "course_search", {**args, "query": "RAG Agent"})
    qa = _tool_json(ctx, "course_question_answer", {**args, "question": "RAG 和 Agent 在学习系统里怎么配合？"})
    cards = _tool_json(ctx, "knowledge_cards_generate", args)
    guide = _tool_json(ctx, "learning_guide_get", {**args, "mode": "self_check", "lecture_sequence": 1})
    visual = _tool_json(ctx, "course_visual_evidence_send", {**args, "query": "Agent"})
    note = _tool_json(ctx, "note_create", {**args, "lecture_sequence": 1, "body": "Hermes path can write a learner note."})
    progress = _tool_json(ctx, "reading_progress_set", {**args, "lecture_sequence": 1, "status": "read"})

    qa_answer = qa.get("answer") if isinstance(qa.get("answer"), dict) else qa
    return {
        "status": "passed",
        "registered_tool_count": len(ctx.tools),
        "coverage_ratio": (coverage.get("coverage") or {}).get("coverage_ratio"),
        "reader_segment_count": len(((reader.get("reader") or {}).get("segments") or [])),
        "search_result_count": search.get("result_count"),
        "qa_status": qa_answer.get("status"),
        "qa_citation_count": qa_answer.get("citation_count"),
        "card_count": cards.get("card_count"),
        "guide_status": (guide.get("guide") or {}).get("status"),
        "guide_question_count": (guide.get("guide") or {}).get("question_count"),
        "visual_status": visual.get("status"),
        "visual_media_count": str(visual.get("gateway_reply") or "").count("MEDIA:"),
        "note_status": note.get("status"),
        "progress_status": (progress.get("progress") or {}).get("status"),
    }


def _tool_json(ctx: FakeHermesContext, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    raw = ctx.tools[name]["handler"](arguments)
    payload = json.loads(raw)
    if payload.get("status") == "failed":
        raise RuntimeError(f"{name} failed: {payload}")
    return payload


def _hit_lecture_title(hit: dict[str, Any]) -> str:
    citation = hit.get("citation") if isinstance(hit.get("citation"), dict) else {}
    return str(hit.get("lecture_title") or citation.get("lecture_title") or "")


def _run_web_path(repo: Path, store_root: Path, course_id: str, *, port: int) -> dict[str, Any]:
    server_path = repo / "apps" / "web" / "server.py"
    process = subprocess.Popen(
        [
            sys.executable,
            str(server_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--store-root",
            str(store_root),
        ],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_web(base_url)
        courses = _http_json(f"{base_url}/api/courses")
        coverage = _http_json(f"{base_url}/api/coverage?course_id={course_id}")
        reader = _http_json(f"{base_url}/api/reader?course_id={course_id}&lecture_sequence=1")
        search = _http_json(f"{base_url}/api/search?course_id={course_id}&query=RAG%20Agent")
        qa = _http_json(
            f"{base_url}/api/qa?course_id={course_id}&question=RAG%20%E5%92%8C%20Agent%20%E5%A6%82%E4%BD%95%E9%85%8D%E5%90%88"
        )
        guide = _http_json(f"{base_url}/api/guide?course_id={course_id}&mode=self_check&lecture_sequence=1")
        notes = _http_json(f"{base_url}/api/notes?course_id={course_id}")
        bookmarks = _http_json(f"{base_url}/api/bookmarks?course_id={course_id}")
        progress = _http_json(f"{base_url}/api/progress?course_id={course_id}")
        qa_answer = qa.get("answer") if isinstance(qa.get("answer"), dict) else qa
        return {
            "status": "passed",
            "base_url": base_url,
            "course_count": len(courses.get("courses") or []),
            "coverage_ratio": (coverage.get("coverage") or {}).get("coverage_ratio"),
            "reader_segment_count": len(reader.get("segments") or []),
            "search_result_count": search.get("result_count"),
            "qa_status": qa_answer.get("status"),
            "qa_citation_count": qa_answer.get("citation_count"),
            "guide_status": guide.get("status"),
            "guide_question_count": guide.get("question_count"),
            "note_count": notes.get("note_count"),
            "bookmark_count": bookmarks.get("bookmark_count"),
            "progress_count": progress.get("progress_count"),
        }
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def _wait_for_web(base_url: str) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            _http_json(f"{base_url}/api/courses")
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"Web server did not become ready: {base_url}")


def _http_json(url: str) -> dict[str, Any]:
    with request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _assert_report(report: dict[str, Any]) -> None:
    checks = {
        "coverage": report["coverage"]["coverage_ratio"] == 1.0,
        "search": report["search"]["result_count"] >= 1,
        "cards": report["cards"]["card_count"] >= 1,
        "hermes": report["hermes"]["status"] == "passed",
        "hermes_visual": report["hermes"]["visual_media_count"] == 1,
        "web": report["web"]["status"] == "passed",
        "web_qa": report["web"]["qa_citation_count"] >= 1,
        "workspace": report["workspace"]["progress_status"] == "read",
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"Interaction smoke failed checks: {', '.join(failed)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Course2Knowledge Lite deploy interaction smoke.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--profile-root", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--port", type=int, default=3191)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_interaction_smoke(
        repo_root=args.repo_root,
        store_root=args.store_root,
        profile_root=args.profile_root,
        output=args.output,
        port=args.port,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
