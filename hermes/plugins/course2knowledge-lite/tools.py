from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from course2knowledge_lite_bilibili import (
    import_collection_skeleton_to_store,
    import_lecture_transcript_to_store,
)
from course2knowledge_lite_store import JsonCourseStore


TOOLSET = "course2knowledge-lite"
TOOL_NAMES = [
    "collection_import_start",
    "import_status_get",
    "lecture_transcript_import",
]


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _store_root(arguments: dict[str, Any]) -> Path:
    configured = str(arguments.get("store_root", "") or os.environ.get("COURSE2KNOWLEDGE_STORE_ROOT", "") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return _repo_root() / "data" / "course-store"


def _tool_error(tool_name: str, exc: Exception) -> str:
    return _json_response(
        {
            "status": "failed",
            "tool": tool_name,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    )


def _collection_import_start_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        result = import_collection_skeleton_to_store(
            str(arguments.get("source_url", "") or "").strip(),
            store_root=_store_root(arguments),
        )
        return _json_response({"status": "completed", "tool": "collection_import_start", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("collection_import_start", exc)


def _import_status_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        import_id = str(arguments.get("import_id", "") or "").strip()
        if not import_id:
            raise ValueError("import_id is required")
        payload = JsonCourseStore(_store_root(arguments)).read_import_status(import_id)
        return _json_response({"status": "completed", "tool": "import_status_get", "import_status": payload})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("import_status_get", exc)


def _lecture_transcript_import_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        course_id = str(arguments.get("course_id", "") or "").strip()
        lecture = dict(arguments.get("lecture") or {})
        if not course_id:
            raise ValueError("course_id is required")
        result = import_lecture_transcript_to_store(
            store_root=_store_root(arguments),
            course_id=course_id,
            lecture=lecture,
        )
        return _json_response({"status": "completed", "tool": "lecture_transcript_import", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("lecture_transcript_import", exc)


def _collection_import_start_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "source_url": {"type": "string", "description": "Bilibili collection URL."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["source_url"],
        "additionalProperties": False,
    }


def _import_status_get_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "import_id": {"type": "string", "description": "Import status id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["import_id"],
        "additionalProperties": False,
    }


def _lecture_transcript_import_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "Local course id."},
            "lecture": {"type": "object", "description": "Lecture record from the local course store."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["course_id", "lecture"],
        "additionalProperties": False,
    }


def _tool_schema(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": parameters,
    }


def register_course2knowledge_lite_tools(ctx: Any) -> None:
    ctx.register_tool(
        name="collection_import_start",
        toolset=TOOLSET,
        schema=_tool_schema(
            "collection_import_start",
            "Expand a Bilibili collection and create a local course skeleton.",
            _collection_import_start_schema(),
        ),
        handler=_collection_import_start_handler,
        description="Start a public Lite Bilibili collection import.",
    )
    ctx.register_tool(
        name="import_status_get",
        toolset=TOOLSET,
        schema=_tool_schema(
            "import_status_get",
            "Read a local Course2Knowledge Lite import status record.",
            _import_status_get_schema(),
        ),
        handler=_import_status_get_handler,
        description="Read a public Lite import status.",
    )
    ctx.register_tool(
        name="lecture_transcript_import",
        toolset=TOOLSET,
        schema=_tool_schema(
            "lecture_transcript_import",
            "Import one lecture's Bilibili transcript into the local course store.",
            _lecture_transcript_import_schema(),
        ),
        handler=_lecture_transcript_import_handler,
        description="Import one public Lite lecture transcript.",
    )
