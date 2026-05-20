from __future__ import annotations

import importlib.util

from .runtime_paths import resolve_runtime_root


ROOT = resolve_runtime_root("scripts/deploy_interaction_smoke.py")
SCRIPT_PATH = ROOT / "scripts" / "deploy_interaction_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("deploy_interaction_smoke", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load deploy interaction smoke script: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_interaction_smoke(*, repo_root, store_root, profile_root, output="", port=3191):
    module = _load_module()
    return module.run_interaction_smoke(
        repo_root=repo_root,
        store_root=store_root,
        profile_root=profile_root,
        output=output,
        port=port,
    )
