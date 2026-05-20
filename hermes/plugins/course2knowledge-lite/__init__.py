"""Course2Knowledge Lite Hermes plugin."""

from __future__ import annotations

import sys
from pathlib import Path

from .runtime import resolve_repo_root


def _repo_root() -> Path:
    return resolve_repo_root(__file__)


def _bootstrap_public_packages() -> None:
    repo_root = _repo_root()
    package_roots = [
        repo_root / "packages" / "bilibili-import" / "src",
        repo_root / "packages" / "course-store" / "src",
        repo_root / "packages" / "qa" / "src",
        repo_root / "packages" / "guidance" / "src",
    ]
    for package_root in package_roots:
        text_path = str(package_root)
        if text_path not in sys.path:
            sys.path.insert(0, text_path)


_bootstrap_public_packages()

from .tools import register_course2knowledge_lite_tools


def register(ctx):
    register_course2knowledge_lite_tools(ctx)
