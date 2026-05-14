from __future__ import annotations

import json
import os
from pathlib import Path


ENV_REPO_ROOT = "COURSE2KNOWLEDGE_LITE_REPO_ROOT"
METADATA_FILE = "course2knowledge_lite_repo_root.json"


def resolve_repo_root(anchor: str | Path | None = None) -> Path:
    configured = os.environ.get(ENV_REPO_ROOT, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    current = Path(anchor or __file__).resolve()
    search_dirs = [current.parent, *current.parents]
    for directory in search_dirs:
        metadata_path = directory / METADATA_FILE
        if not metadata_path.exists():
            continue
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        repo_root = str(payload.get("repo_root") or "").strip()
        if repo_root:
            return Path(repo_root).expanduser().resolve()

    return current.parents[3]

