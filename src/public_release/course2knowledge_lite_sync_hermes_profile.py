from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "sync_hermes_lite_profile.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sync_hermes_lite_profile", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Hermes profile sync script: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sync_profile(**kwargs):
    module = _load_module()
    return module.sync_profile(**kwargs)
