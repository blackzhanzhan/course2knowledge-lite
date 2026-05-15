from __future__ import annotations

import importlib.util

from .runtime_paths import resolve_runtime_root

ROOT = resolve_runtime_root("apps/web/server.py")
SERVER_PATH = ROOT / "apps" / "web" / "server.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("course2knowledge_lite_web_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Web Lite server: {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    module = _load_module()
    return module.main(argv)
