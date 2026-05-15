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
    "course_transcript_coverage_get",
    "knowledge_cards_generate",
    "knowledge_card_list",
    "knowledge_card_get",
    "course_visual_evidence_send",
    "lecture_reader_get",
    "course_search",
    "course_question_answer",
    "note_create",
    "note_list",
    "note_update",
    "note_delete",
    "bookmark_create",
    "bookmark_list",
    "bookmark_delete",
    "reading_progress_set",
    "reading_progress_get",
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


def _resolve_course_id(arguments: dict[str, Any], store: JsonCourseStore) -> str:
    course_id = str(arguments.get("course_id", "") or "").strip()
    if course_id:
        return course_id
    courses_root = store.root / "courses"
    if not courses_root.exists():
        raise ValueError("No imported course is available yet. Import a Bilibili collection first.")
    candidates: list[dict[str, str]] = []
    for course_root in sorted(courses_root.iterdir(), key=lambda item: item.name):
        if not course_root.is_dir():
            continue
        course_path = course_root / "course.json"
        if not course_path.exists():
            continue
        course = json.loads(course_path.read_text(encoding="utf-8"))
        if not isinstance(course, dict):
            continue
        resolved_id = str(course.get("course_id") or course_root.name).strip()
        if resolved_id:
            candidates.append(
                {
                    "course_id": resolved_id,
                    "title": str(course.get("title") or resolved_id).strip(),
                }
            )
    if len(candidates) == 1:
        return candidates[0]["course_id"]
    if not candidates:
        raise ValueError("No imported course is available yet. Import a Bilibili collection first.")
    titles = ", ".join(item["title"] for item in candidates[:5])
    raise ValueError(f"I found multiple imported courses. Please mention which course you mean: {titles}")


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


def _course_transcript_coverage_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        coverage = store.summarize_transcript_coverage(course_id)
        return _json_response(
            {
                "status": "completed",
                "tool": "course_transcript_coverage_get",
                "coverage": coverage,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("course_transcript_coverage_get", exc)


def _knowledge_cards_generate_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        result = store.generate_knowledge_cards(
            course_id,
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
            overwrite=_bool_argument(arguments.get("overwrite"), default=True),
        )
        return _json_response({"status": "completed", "tool": "knowledge_cards_generate", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("knowledge_cards_generate", exc)


def _knowledge_card_list_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = str(arguments.get("lecture_id", "") or "").strip()
        cards = store.list_knowledge_cards(course_id=course_id, lecture_id=lecture_id)
        return _json_response(
            {
                "status": "completed",
                "tool": "knowledge_card_list",
                "course_id": course_id,
                "cards": cards,
                "card_count": len(cards),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("knowledge_card_list", exc)


def _knowledge_card_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        card = store.read_knowledge_card(
            _resolve_course_id(arguments, store),
            _required_text(arguments, "card_id"),
        )
        return _json_response({"status": "completed", "tool": "knowledge_card_get", "card": card})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("knowledge_card_get", exc)


def _course_visual_evidence_send_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        if "image_path" in arguments:
            raise ValueError("image_path is not accepted; select an existing visual evidence record")
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = str(arguments.get("lecture_id", "") or "").strip()
        lecture_sequence = arguments.get("lecture_sequence")
        if not lecture_id and lecture_sequence not in (None, ""):
            lecture_id = str(store.read_lecture_reader(course_id, lecture_sequence=lecture_sequence)["lecture"]["lecture_id"])
        visual = store.select_visual_evidence(
            course_id=course_id,
            visual_id=str(arguments.get("visual_id", "") or "").strip(),
            lecture_id=lecture_id,
            query=str(arguments.get("query", "") or "").strip(),
        )
        media_path = _resolve_public_media_path(str(visual.get("image_path") or ""))
        explanation = _visual_evidence_explanation(visual)
        media_directive = f"MEDIA:{media_path}"
        return _json_response(
            {
                "status": "completed",
                "tool": "course_visual_evidence_send",
                "course_id": course_id,
                "visual_evidence": visual,
                "media_path": media_path,
                "media_directive": media_directive,
                "gateway_reply": f"{explanation}\n{media_directive}",
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("course_visual_evidence_send", exc)


def _lecture_reader_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        payload = store.read_lecture_reader(
            course_id,
            lecture_sequence=arguments.get("lecture_sequence"),
            lecture_id=str(arguments.get("lecture_id", "") or "").strip(),
        )
        return _json_response({"status": "completed", "tool": "lecture_reader_get", "reader": payload})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("lecture_reader_get", exc)


def _course_search_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        query = str(arguments.get("query", "") or "").strip()
        if not query:
            raise ValueError("query is required")
        hits = store.search_transcripts(
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
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        payload = answer_course_question(
            store=store,
            course_id=course_id,
            question=str(arguments.get("question", "") or ""),
            limit=_positive_limit(arguments.get("limit"), default=5),
        )
        return _json_response({"status": "completed", "tool": "course_question_answer", "answer": payload})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("course_question_answer", exc)


def _note_create_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = _lecture_id_from_arguments(store, course_id, arguments)
        note = store.create_note(
            course_id,
            lecture_id,
            str(arguments.get("body", "") or ""),
        )
        return _json_response({"status": "completed", "tool": "note_create", "note": note})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("note_create", exc)


def _note_list_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = str(arguments.get("lecture_id", "") or "").strip()
        notes = store.list_notes(course_id=course_id, lecture_id=lecture_id)
        return _json_response({"status": "completed", "tool": "note_list", "notes": notes, "note_count": len(notes)})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("note_list", exc)


def _note_update_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        note = store.update_note(
            _resolve_course_id(arguments, store),
            _required_text(arguments, "note_id"),
            str(arguments.get("body", "") or ""),
        )
        return _json_response({"status": "completed", "tool": "note_update", "note": note})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("note_update", exc)


def _note_delete_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        result = store.delete_note(
            _resolve_course_id(arguments, store),
            _required_text(arguments, "note_id"),
        )
        return _json_response({"status": "completed", "tool": "note_delete", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("note_delete", exc)


def _bookmark_create_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        bookmark = store.create_bookmark(
            _resolve_course_id(arguments, store),
            _required_text(arguments, "target_type"),
            _required_text(arguments, "target_id"),
        )
        return _json_response({"status": "completed", "tool": "bookmark_create", "bookmark": bookmark})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("bookmark_create", exc)


def _bookmark_list_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        target_type = str(arguments.get("target_type", "") or "").strip()
        bookmarks = store.list_bookmarks(course_id=course_id, target_type=target_type)
        return _json_response(
            {
                "status": "completed",
                "tool": "bookmark_list",
                "bookmarks": bookmarks,
                "bookmark_count": len(bookmarks),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("bookmark_list", exc)


def _bookmark_delete_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        result = store.delete_bookmark(
            _resolve_course_id(arguments, store),
            _required_text(arguments, "bookmark_id"),
        )
        return _json_response({"status": "completed", "tool": "bookmark_delete", **result})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("bookmark_delete", exc)


def _reading_progress_set_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = _lecture_id_from_arguments(store, course_id, arguments)
        progress = store.set_reading_progress(
            course_id,
            lecture_id,
            _required_text(arguments, "status"),
        )
        return _json_response({"status": "completed", "tool": "reading_progress_set", "progress": progress})
    except Exception as exc:  # noqa: BLE001
        return _tool_error("reading_progress_set", exc)


def _reading_progress_get_handler(arguments: dict[str, Any], **_registry_kwargs: Any) -> str:
    try:
        store = JsonCourseStore(_store_root(arguments))
        course_id = _resolve_course_id(arguments, store)
        lecture_id = str(arguments.get("lecture_id", "") or "").strip()
        if lecture_id:
            progress = [store.get_reading_progress(course_id, lecture_id)]
        else:
            progress = store.list_reading_progress(course_id=course_id)
        return _json_response(
            {
                "status": "completed",
                "tool": "reading_progress_get",
                "progress": progress,
                "progress_count": len(progress),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _tool_error("reading_progress_get", exc)


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
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "1-based lecture sequence number in the course.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _course_transcript_coverage_get_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _knowledge_cards_generate_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_id": {
                "type": ["string", "null"],
                "description": "Optional exact local lecture id to generate cards for one lecture.",
            },
            "overwrite": {
                "type": ["boolean", "string", "null"],
                "description": "Whether to replace previously generated source cards. Defaults to true.",
            },
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _knowledge_card_list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id filter."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _knowledge_card_get_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "card_id": {"type": "string", "description": "Local knowledge card id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["card_id"],
        "additionalProperties": False,
    }


def _course_visual_evidence_send_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "visual_id": {
                "type": ["string", "null"],
                "description": "Optional exact visual evidence id. Preferred when known.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id filter."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "Optional 1-based lecture sequence filter.",
            },
            "query": {
                "type": ["string", "null"],
                "description": "Optional topic query used to select a public visual evidence record.",
            },
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _course_search_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "query": {"type": "string", "description": "Transcript search query."},
            "limit": {"type": ["integer", "string", "null"], "description": "Maximum result count."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["query"],
        "additionalProperties": False,
    }


def _course_question_answer_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "question": {"type": "string", "description": "Question to answer from transcript evidence."},
            "limit": {"type": ["integer", "string", "null"], "description": "Maximum citation count."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["question"],
        "additionalProperties": False,
    }


def _note_create_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "Optional 1-based lecture sequence number.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "body": {"type": "string", "description": "Learner-authored note body."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["body"],
        "additionalProperties": False,
    }


def _note_list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id filter."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _note_update_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "note_id": {"type": "string", "description": "Local note id."},
            "body": {"type": "string", "description": "Replacement note body."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["note_id", "body"],
        "additionalProperties": False,
    }


def _note_delete_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "note_id": {"type": "string", "description": "Local note id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["note_id"],
        "additionalProperties": False,
    }


def _bookmark_create_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "target_type": {"type": "string", "enum": ["lecture", "segment", "card"]},
            "target_id": {"type": "string", "description": "Lecture, segment, or card id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["target_type", "target_id"],
        "additionalProperties": False,
    }


def _bookmark_list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "target_type": {"type": ["string", "null"], "description": "Optional bookmark target type filter."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _bookmark_delete_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "bookmark_id": {"type": "string", "description": "Local bookmark id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["bookmark_id"],
        "additionalProperties": False,
    }


def _reading_progress_set_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_sequence": {
                "type": ["integer", "string", "null"],
                "description": "Optional 1-based lecture sequence number.",
            },
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "status": {"type": "string", "enum": ["not_started", "reading", "read"]},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "required": ["status"],
        "additionalProperties": False,
    }


def _reading_progress_get_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "course_id": {"type": ["string", "null"], "description": "Optional local course id."},
            "lecture_id": {"type": ["string", "null"], "description": "Optional exact local lecture id."},
            "store_root": {"type": ["string", "null"], "description": "Optional local JSON store root."},
        },
        "additionalProperties": False,
    }


def _required_text(arguments: dict[str, Any], name: str) -> str:
    value = str(arguments.get(name, "") or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _lecture_id_from_arguments(store: JsonCourseStore, course_id: str, arguments: dict[str, Any]) -> str:
    lecture_id = str(arguments.get("lecture_id", "") or "").strip()
    if lecture_id:
        return lecture_id
    lecture_sequence = arguments.get("lecture_sequence")
    if lecture_sequence not in (None, ""):
        return str(store.read_lecture_reader(course_id, lecture_sequence=lecture_sequence)["lecture"]["lecture_id"])
    raise ValueError("lecture_id or lecture_sequence is required")


def _positive_limit(raw_value: Any, *, default: int) -> int:
    if raw_value in (None, ""):
        return default
    try:
        return max(int(raw_value), 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"limit must be an integer: {raw_value}") from exc


def _bool_argument(raw_value: Any, *, default: bool) -> bool:
    if raw_value in (None, ""):
        return default
    if isinstance(raw_value, bool):
        return raw_value
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"boolean value expected: {raw_value}")


def _resolve_public_media_path(relative_image_path: str) -> str:
    cleaned = str(relative_image_path or "").strip().replace("\\", "/")
    if not cleaned:
        raise ValueError("visual evidence image_path is missing")
    raw_path = Path(cleaned)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ValueError("visual evidence image_path must be a repo-local relative path")
    repo_root = _repo_root().resolve()
    media_path = (repo_root / cleaned).resolve()
    if not _is_relative_to(media_path, repo_root):
        raise ValueError("visual evidence image_path resolved outside the public repo")
    if not media_path.exists() or not media_path.is_file():
        raise ValueError(f"visual evidence image file is missing: {cleaned}")
    return str(media_path).replace("\\", "/")


def _visual_evidence_explanation(visual: dict[str, Any]) -> str:
    title = str(visual.get("title") or "Course visual evidence").strip()
    explanation = str(visual.get("explanation") or "").strip()
    provenance = str(visual.get("provenance") or "").strip()
    source_url = str(visual.get("source_url") or "").strip()
    lines = [title]
    if explanation:
        lines.append(explanation)
    if provenance:
        lines.append(f"Evidence: {provenance}")
    if source_url:
        lines.append(f"Source: {source_url}")
    return "\n".join(lines)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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
        name="course_transcript_coverage_get",
        toolset=TOOLSET,
        schema=_tool_schema(
            "course_transcript_coverage_get",
            "Summarize transcript coverage for a local Course2Knowledge Lite course.",
            _course_transcript_coverage_get_schema(),
        ),
        handler=_course_transcript_coverage_get_handler,
        description="Summarize public Lite transcript coverage.",
    )
    ctx.register_tool(
        name="knowledge_cards_generate",
        toolset=TOOLSET,
        schema=_tool_schema(
            "knowledge_cards_generate",
            "Generate conservative source-linked knowledge cards from local transcript segments.",
            _knowledge_cards_generate_schema(),
        ),
        handler=_knowledge_cards_generate_handler,
        description="Generate public Lite knowledge cards from transcript evidence.",
    )
    ctx.register_tool(
        name="knowledge_card_list",
        toolset=TOOLSET,
        schema=_tool_schema(
            "knowledge_card_list",
            "List generated or learner-visible local knowledge cards for a course.",
            _knowledge_card_list_schema(),
        ),
        handler=_knowledge_card_list_handler,
        description="List public Lite knowledge cards.",
    )
    ctx.register_tool(
        name="knowledge_card_get",
        toolset=TOOLSET,
        schema=_tool_schema(
            "knowledge_card_get",
            "Read one source-linked local knowledge card.",
            _knowledge_card_get_schema(),
        ),
        handler=_knowledge_card_get_handler,
        description="Read a public Lite knowledge card.",
    )
    ctx.register_tool(
        name="course_visual_evidence_send",
        toolset=TOOLSET,
        schema=_tool_schema(
            "course_visual_evidence_send",
            "Select public course-bound visual evidence and return explanation text plus one MEDIA directive.",
            _course_visual_evidence_send_schema(),
        ),
        handler=_course_visual_evidence_send_handler,
        description="Send public Lite visual evidence through Hermes MEDIA reply format.",
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
    ctx.register_tool(
        name="note_create",
        toolset=TOOLSET,
        schema=_tool_schema(
            "note_create",
            "Create a learner-authored note for one stored lecture.",
            _note_create_schema(),
        ),
        handler=_note_create_handler,
        description="Create a public Lite lecture note.",
    )
    ctx.register_tool(
        name="note_list",
        toolset=TOOLSET,
        schema=_tool_schema(
            "note_list",
            "List learner-authored notes for a local course.",
            _note_list_schema(),
        ),
        handler=_note_list_handler,
        description="List public Lite notes.",
    )
    ctx.register_tool(
        name="note_update",
        toolset=TOOLSET,
        schema=_tool_schema(
            "note_update",
            "Update a learner-authored note.",
            _note_update_schema(),
        ),
        handler=_note_update_handler,
        description="Update a public Lite note.",
    )
    ctx.register_tool(
        name="note_delete",
        toolset=TOOLSET,
        schema=_tool_schema(
            "note_delete",
            "Delete a learner-authored note.",
            _note_delete_schema(),
        ),
        handler=_note_delete_handler,
        description="Delete a public Lite note.",
    )
    ctx.register_tool(
        name="bookmark_create",
        toolset=TOOLSET,
        schema=_tool_schema(
            "bookmark_create",
            "Create a lecture, segment, or card bookmark in the local course store.",
            _bookmark_create_schema(),
        ),
        handler=_bookmark_create_handler,
        description="Create a public Lite bookmark.",
    )
    ctx.register_tool(
        name="bookmark_list",
        toolset=TOOLSET,
        schema=_tool_schema(
            "bookmark_list",
            "List bookmarks for a local course.",
            _bookmark_list_schema(),
        ),
        handler=_bookmark_list_handler,
        description="List public Lite bookmarks.",
    )
    ctx.register_tool(
        name="bookmark_delete",
        toolset=TOOLSET,
        schema=_tool_schema(
            "bookmark_delete",
            "Delete a local bookmark.",
            _bookmark_delete_schema(),
        ),
        handler=_bookmark_delete_handler,
        description="Delete a public Lite bookmark.",
    )
    ctx.register_tool(
        name="reading_progress_set",
        toolset=TOOLSET,
        schema=_tool_schema(
            "reading_progress_set",
            "Set lightweight reading progress for one lecture.",
            _reading_progress_set_schema(),
        ),
        handler=_reading_progress_set_handler,
        description="Set public Lite lecture reading progress.",
    )
    ctx.register_tool(
        name="reading_progress_get",
        toolset=TOOLSET,
        schema=_tool_schema(
            "reading_progress_get",
            "Read lightweight reading progress for a course or lecture.",
            _reading_progress_get_schema(),
        ),
        handler=_reading_progress_get_handler,
        description="Read public Lite reading progress.",
    )
