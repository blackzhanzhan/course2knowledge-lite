from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_store_root() -> Path:
    return _repo_root() / "data" / "course-store"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill explicit visual keyframe readiness for Course2Knowledge Lite imports."
    )
    parser.add_argument("--store-root", default=str(_default_store_root()))
    parser.add_argument("--course-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--unavailable-reason", default="missing_source_media")
    parser.add_argument("--now", default="")
    args = parser.parse_args()

    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root / "packages" / "course-store" / "src"))

    from course2knowledge_lite_store import SQLiteCourseStore  # noqa: PLC0415

    store = SQLiteCourseStore(Path(args.store_root).expanduser())
    explicit_course_id = str(args.course_id or "").strip()
    course_ids = [explicit_course_id] if explicit_course_id else [
        str(course.get("course_id") or "") for course in store.list_courses()
    ]
    results = [
        store.backfill_visual_keyframe_status(
            course_id,
            run_id=str(args.run_id or "").strip(),
            unavailable_reason=str(args.unavailable_reason or "").strip(),
            now=str(args.now or "").strip(),
        )
        for course_id in course_ids
        if course_id
    ]
    print(
        json.dumps(
            {
                "status": "completed",
                "store_root": str(store.root),
                "course_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
