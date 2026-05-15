from __future__ import annotations

from pathlib import Path
import sysconfig


def resolve_runtime_root(required_relative_path: str) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    required_path = Path(required_relative_path)
    if (source_root / required_path).exists():
        return source_root

    data_root = Path(sysconfig.get_path("data")) / "course2knowledge_lite_runtime"
    if (data_root / required_path).exists():
        return data_root

    raise RuntimeError(
        "Could not locate Course2Knowledge Lite runtime assets. "
        f"Expected {required_relative_path} under source root or installed data root."
    )
