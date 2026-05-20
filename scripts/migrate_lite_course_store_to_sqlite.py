#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate Course2Knowledge Lite public JSON demo data into SQLite.")
    parser.add_argument("--source-root", default=str(_repo_root() / "data" / "course-store"))
    parser.add_argument("--target-root", default=str(_repo_root() / "data" / "course-store"))
    parser.add_argument(
        "--no-reset",
        action="store_false",
        dest="reset",
        help="Keep an existing SQLite database instead of replacing it first.",
    )
    parser.set_defaults(reset=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root / "packages" / "course-store" / "src"))
    from course2knowledge_lite_store import JsonCourseStore, SQLiteCourseStore

    source_root = Path(args.source_root).expanduser().resolve()
    target_root = Path(args.target_root).expanduser().resolve()
    source_store = JsonCourseStore(source_root)
    target_store = SQLiteCourseStore(target_root)

    if args.reset and target_store.db_path.exists():
        target_store.db_path.unlink()

    report = target_store.import_from_json_store(source_store)
    print(json.dumps({**report, "source_root": str(source_root), "target_root": str(target_root)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
