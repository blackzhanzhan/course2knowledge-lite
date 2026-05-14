from __future__ import annotations

import json
from typing import Any, Callable


TOOLSET = "course2knowledge-lite"
TOOL_NAMES = [
    "collection_import_start",
    "import_status_get",
    "lecture_transcript_import",
]


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _not_implemented_handler(tool_name: str) -> Callable[..., str]:
    def handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
        return _json_response(
            {
                "status": "not_implemented",
                "tool": tool_name,
                "arguments": dict(arguments or {}),
                "message": "Tool registration surface is present; package wiring follows in the next slice.",
            }
        )

    return handler


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
        handler=_not_implemented_handler("collection_import_start"),
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
        handler=_not_implemented_handler("import_status_get"),
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
        handler=_not_implemented_handler("lecture_transcript_import"),
        description="Import one public Lite lecture transcript.",
    )
