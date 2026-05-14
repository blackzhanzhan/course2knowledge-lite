from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .runtime import resolve_repo_root
from course2knowledge_lite_bilibili import (
    import_collection_skeleton_to_store,
    import_lecture_transcript_by_reference_to_store,
    import_lecture_transcript_to_store,
    import_manual_transcript_by_reference_to_store,
    probe_lecture_transcript_source_by_reference,
)
from course2knowledge_lite_qa import answer_course_question
from course2knowledge_lite_store import JsonCourseStore


TOOLSET = "course2knowledge-lite"
TOOL_NAMES = [
    "collection_import_start",
    "import_status_get",
    "lecture_transcript_import",
    "lecture_transcript_import_by_ref",
    "lecture_transcript_source_probe",
    "manual_transcript_import",
    "lecture_reader_get",
    "course_search",
    "course_question_answer",
]


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _repo_root() -> Path:
    return resolve_repo_root(__file__)


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


def _lecture_transcript_import_by_ref_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        result = import_lecture_transcript_by_reference_to_store(
            store_root=_store_root(arguments),
            course_id=str(arguments.get("course_id", "") or "").strip(),
            import_id=str(arguments.get("import_id", "") or "").strip(),
            lecture_sequence=arguments.get("lecture_sequence"),
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
            source_id=str(arguments.get("source_id", "") or "").strip(),
        )
        return _json_response({"status": "completed", "tool": "lecture_transcript_import_by_ref", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("lecture_transcript_import_by_ref", exc)


def _lecture_transcript_source_probe_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        result = probe_lecture_transcript_source_by_reference(
            store_root=_store_root(arguments),
            course_id=str(arguments.get("course_id", "") or "").strip(),
            import_id=str(arguments.get("import_id", "") or "").strip(),
            lecture_sequence=arguments.get("lecture_sequence"),
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
            source_id=str(arguments.get("source_id", "") or "").strip(),
        )
        return _json_response({"status": "completed", "tool": "lecture_transcript_source_probe", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("lecture_transcript_source_probe", exc)


def _manual_transcript_import_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        result = import_manual_transcript_by_reference_to_store(
            store_root=_store_root(arguments),
            transcript_text=str(arguments.get("transcript_text", "") or ""),
            course_id=str(arguments.get("course_id", "") or "").strip(),
            import_id=str(arguments.get("import_id", "") or "").strip(),
            lecture_sequence=arguments.get("lecture_sequence"),
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
            source_id=str(arguments.get("source_id", "") or "").strip(),
        )
        return _json_response({"status": "completed", "tool": "manual_transcript_import", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("manual_transcript_import", exc)


def _lecture_reader_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        course_id = str(arguments.get("course_id", "") or "").strip()
        if not course_id:
            raise ValueError("course_id is required")
        payload = JsonCourseStore(_store_root(arguments)).read_lecture_reader(
            course_id,
            lecture_sequence=arguments.get("lecture_sequence"),
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
        )
        return _json_response({"status": "completed", "tool": "lecture_reader_get", "reader": payload})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("lecture_reader_get", exc)


def _course_search_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        course_id = str(arguments.get("course_id", "") or "").strip()
        query = str(arguments.get("query", "") or "").strip()
        if not course_id:
            raise ValueError("course_id is required")
        if not query:
            raise ValueError("query is required")
        hits = JsonCourseStore(_store_root(arguments)).search_transcripts(
            course_id,
            query,
            limit=_positive_limit(arguments.get("limit"), default=10),
        )
        return _json_response(
            {
                "status": "completed",
                "tool": "course_search",
                "course_id": course_id,
                "query": query,
                "results": hits,
                "result_count": len(hits),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("course_search", exc)


def _course_question_answer_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        course_id = str(arguments.get("course_id", "") or "").strip()
        if not course_id:
            raise ValueError("course_id is required")
        payload = answer_course_question(
            store=JsonCourseStore(_store_root(arguments)),
            course_id=course_id,
            question=str(arguments.get("question", "") or ""),
            limit=_positive_limit(arguments.get("limit"), default=5),
        )
        return _json_response({"status": "completed", "tool": "course_question_answer", "answer": payload})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("course_question_answer", exc)


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


def _lecture_transcript_import_by_ref_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "import_id": {
                "type": ["string", "null"],
                "description": "Import receipt id returned by collection_import_start.",
            },
            "course_id": {"type": ["string", "null"], "description": "Local course id."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "1-based lecture sequence number in the course.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "source_id": {"type": ["string", "null"], "description": "Optional Bilibili BV id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _manual_transcript_import_schema() -> dict[str, Any]:
    schema = _lecture_transcript_import_by_ref_schema()
    schema["properties"] = {
        **schema["properties"],
        "transcript_text": {
            "type": "string",
            "description": "User-provided transcript text to split into local transcript segments.",
        },
    }
    schema["required"] = ["transcript_text"]
    return schema


def _lecture_reader_get_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "Local course id."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "1-based lecture sequence number in the course.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["course_id"],
        "additionalProperties": False,
    }


def _course_search_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "Local course id."},
            "query": {"type": "string", "description": "Transcript search query."},
            "limit": {"type": ["integer", "string", "null"], "description": "Maximum result count."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["course_id", "query"],
        "additionalProperties": False,
    }


def _course_question_answer_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": "string", "description": "Local course id."},
            "question": {"type": "string", "description": "Question to answer from transcript evidence."},
            "limit": {"type": ["integer", "string", "null"], "description": "Maximum citation count."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["course_id", "question"],
        "additionalProperties": False,
    }


def _positive_limit(raw_value: Any, *, default: int) -> int:
    if raw_value in (None, ""):
        return default
    try:
        return max(int(raw_value), 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"limit must be an integer: {raw_value}") from exc


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
    ctx.register_tool(
        name="lecture_transcript_import_by_ref",
        toolset=TOOLSET,
        schema=_tool_schema(
            "lecture_transcript_import_by_ref",
            "Import one Bilibili lecture transcript by import id, course id, sequence, lecture id, or BV id.",
            _lecture_transcript_import_by_ref_schema(),
        ),
        handler=_lecture_transcript_import_by_ref_handler,
        description="Import one public Lite lecture transcript by course reference.",
    )
    ctx.register_tool(
        name="lecture_transcript_source_probe",
        toolset=TOOLSET,
        schema=_tool_schema(
            "lecture_transcript_source_probe",
            "Check whether one stored Bilibili lecture exposes importable subtitle metadata.",
            _lecture_transcript_import_by_ref_schema(),
        ),
        handler=_lecture_transcript_source_probe_handler,
        description="Probe one public Lite lecture transcript source before import.",
    )
    ctx.register_tool(
        name="manual_transcript_import",
        toolset=TOOLSET,
        schema=_tool_schema(
            "manual_transcript_import",
            "Import user-provided transcript text into one stored lecture as local transcript segments.",
            _manual_transcript_import_schema(),
        ),
        handler=_manual_transcript_import_handler,
        description="Import user-provided transcript text for one public Lite lecture.",
    )
    ctx.register_tool(
        name="lecture_reader_get",
        toolset=TOOLSET,
        schema=_tool_schema(
            "lecture_reader_get",
            "Read one lecture's transcript payload for Web or Feishu reading surfaces.",
            _lecture_reader_get_schema(),
        ),
        handler=_lecture_reader_get_handler,
        description="Read a public Lite lecture transcript payload.",
    )
    ctx.register_tool(
        name="course_search",
        toolset=TOOLSET,
        schema=_tool_schema(
            "course_search",
            "Search local transcript segments and return citation-ready results.",
            _course_search_schema(),
        ),
        handler=_course_search_handler,
        description="Search public Lite course transcript evidence.",
    )
    ctx.register_tool(
        name="course_question_answer",
        toolset=TOOLSET,
        schema=_tool_schema(
            "course_question_answer",
            "Answer a course question from local transcript evidence with citations.",
            _course_question_answer_schema(),
        ),
        handler=_course_question_answer_handler,
        description="Answer public Lite course questions with citations.",
    )
