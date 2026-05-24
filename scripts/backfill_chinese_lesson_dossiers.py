from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_store_root() -> Path:
    return _repo_root() / "data" / "course-store"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Chinese generated notes and knowledge atoms for Course2Knowledge Lite.")
    parser.add_argument("--store-root", default=str(_default_store_root()))
    parser.add_argument("--course-id", default="")
    parser.add_argument("--lecture-id", default="")
    parser.add_argument("--now", default="")
    parser.add_argument("--compile-mode", choices=["fallback", "auto", "model"], default="model")
    parser.add_argument("--compile-provider", default="deepseek")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-chunk-workers", type=int, default=1)
    parser.add_argument("--max-concurrent-requests", type=int, default=1)
    parser.add_argument("--fast-map-mode", action="store_true", default=True)
    parser.add_argument("--split-map-mode", action="store_true", default=True)
    parser.add_argument("--no-fast-map-mode", action="store_true")
    parser.add_argument("--no-split-map-mode", action="store_true")
    parser.add_argument("--no-fast-reduce-mode", action="store_true")
    parser.add_argument("--lite-map-mode", action="store_true")
    parser.add_argument("--skip-model-ready", action="store_true")
    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root / "packages" / "course-store" / "src"))
    sys.path.insert(0, str(repo_root / "packages" / "bilibili-import" / "src"))

    from course2knowledge_lite_bilibili.handoff import _upsert_generated_lesson_note  # noqa: PLC0415
    from course2knowledge_lite_store import SQLiteCourseStore  # noqa: PLC0415

    store = SQLiteCourseStore(Path(args.store_root).expanduser())
    explicit_course_id = str(args.course_id or "").strip()
    course_ids = [explicit_course_id] if explicit_course_id else [
        str(course.get("course_id") or "") for course in store.list_courses()
    ]
    touched: list[dict[str, Any]] = []
    for course_id in [item for item in course_ids if item]:
        lectures = store.read_lectures(course_id)
        explicit_lecture_id = str(args.lecture_id or "").strip()
        if explicit_lecture_id:
            lectures = [lecture for lecture in lectures if str(lecture.get("lecture_id") or "") == explicit_lecture_id]
        for lecture in lectures:
            lecture_id = str(lecture.get("lecture_id") or "")
            segments = store.read_transcript_segments_if_exists(course_id, lecture_id)
            if not segments:
                continue
            if args.skip_model_ready and args.compile_mode == "model" and _has_model_note(store, course_id, lecture_id):
                touched.append(
                    {
                        "course_id": course_id,
                        "lecture_id": lecture_id,
                        "status": "skipped_model_ready",
                    }
                )
                continue
            note_result = _upsert_generated_lesson_note(
                store,
                course_id=course_id,
                lecture=lecture,
                run_id="lite_chinese_dossier_backfill",
                now=str(args.now or "").strip(),
                compile_mode=args.compile_mode,
                compile_provider=str(args.compile_provider or "").strip() or None,
                model=str(args.model or "").strip() or None,
                max_chunk_workers=max(1, int(args.max_chunk_workers or 1)),
                max_concurrent_requests=max(1, int(args.max_concurrent_requests or 1)),
                fast_map_mode=bool(args.fast_map_mode) and not bool(args.no_fast_map_mode),
                split_map_mode=bool(args.split_map_mode) and not bool(args.no_split_map_mode),
                fast_reduce_mode=not bool(args.no_fast_reduce_mode),
                lite_map_mode=bool(args.lite_map_mode),
            )
            note = dict(note_result["note"])
            cards_result = store.upsert_lecture_knowledge_cards_from_dossier(
                course_id,
                lecture=lecture,
                segments=segments,
                dossier=note_result["dossier"],
                overwrite=True,
            )
            touched.append(
                {
                    "course_id": course_id,
                    "lecture_id": lecture_id,
                    "note_id": note["note_id"],
                    "card_count": len(store.list_knowledge_cards(course_id=course_id, lecture_id=lecture_id)),
                    "generated_card_count": int(cards_result.get("generated_card_count") or 0),
                    "compile_mode": args.compile_mode,
                }
            )
    print(json.dumps({"status": "completed", "store_root": str(store.root), "touched": touched}, ensure_ascii=False, indent=2))
    return 0


def _has_model_note(store: Any, course_id: str, lecture_id: str) -> bool:
    try:
        notes = store.list_notes(course_id=course_id, lecture_id=lecture_id)
    except Exception:  # noqa: BLE001
        return False
    for note in notes:
        body = str(note.get("body") or "")
        if "provider: course2knowledge_lite_model_compile" in body:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
