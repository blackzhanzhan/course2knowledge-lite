from __future__ import annotations

import importlib.util

from .runtime_paths import resolve_runtime_root

ROOT = resolve_runtime_root("scripts/smoke_hermes_lite_profile.py")
SCRIPT_PATH = ROOT / "scripts" / "smoke_hermes_lite_profile.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_hermes_lite_profile", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Hermes profile smoke script: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def smoke_profile(profile_root):
    module = _load_module()
    return module.smoke_profile(profile_root)
