from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from typing import Any


OFFICE_TEACHING_ROUTE_TOOL = "studio_office_teaching_route"
OFFICE_ROUTE_TRACE_KIND = "lite_office_route_trace"
OFFICE_ARCHITECTURE_VERSION = "course2knowledge_lite_route_2026_05"


_SCENE_ALIASES = {
    "": "learning",
    "learn": "learning",
    "learning": "learning",
    "teach": "learning",
    "review": "review",
    "recap": "recap",
    "assessment": "assessment",
    "quiz": "assessment",
    "test": "assessment",
}


_LITE_TOOL_OWNERSHIP: dict[str, str] = {
    OFFICE_TEACHING_ROUTE_TOOL: "lite_route_intake",
    "studio_teaching_learning_companion_next": "lite_state_projection",
    "studio_teaching_chat_lesson_capsule": "lite_grounded_teaching",
    "studio_teaching_state_get": "lite_state_projection",
    "studio_teaching_evidence_list": "lite_course_evidence",
    "studio_teaching_context_get": "lite_course_evidence",
}


_LITE_CHAIN: tuple[dict[str, Any], ...] = (
    {
        "office_id": "lite_route_intake",
        "office_name": "lite_route_intake",
        "role": "route_intake",
        "phase": "intake",
        "responsibility": (
            "Normalize learner intent and force the Web frontdesk through a route "
            "contract before any student-facing teaching text is released."
        ),
        "owns": [
            "scene_mode",
            "route_trace",
            "student_surface_boundary",
            "required teaching route tool",
        ],
        "required_tools": [OFFICE_TEACHING_ROUTE_TOOL],
        "forbidden_responsibilities": [
            "formal queue completion",
            "private learner-state writeback",
            "private course authority",
            "student-facing lesson prose",
        ],
        "hands_off_to": "lite_state_projection",
    },
    {
        "office_id": "lite_state_projection",
        "office_name": "lite_state_projection",
        "role": "state_projection",
        "phase": "state_projection",
        "responsibility": (
            "Project the child-local SQLite course, chat history, and atom status "
            "into a teaching packet without writing private mother-project state."
        ),
        "owns": [
            "local chat history",
            "knowledge atom status projection",
            "lesson progress label",
            "read-only course binding hints",
        ],
        "required_tools": [
            "studio_teaching_learning_companion_next",
            "studio_teaching_state_get",
        ],
        "forbidden_responsibilities": [
            "Feishu Base writes",
            "mother learning queue selection",
            "private mastery or review-stage mutation",
        ],
        "hands_off_to": "lite_course_evidence",
    },
    {
        "office_id": "lite_course_evidence",
        "office_name": "lite_course_evidence",
        "role": "course_evidence",
        "phase": "grounding",
        "responsibility": (
            "Bind the turn to child-local course notes, transcript segments, "
            "knowledge cards, and visual evidence."
        ),
        "owns": [
            "course transcript lookup",
            "knowledge card selection",
            "lecture reader context",
            "visual evidence projection",
        ],
        "required_tools": [
            "studio_teaching_evidence_list",
            "studio_teaching_context_get",
        ],
        "forbidden_responsibilities": [
            "model-memory-only teaching",
            "private catalog lookup",
            "formal learner-state completion",
        ],
        "hands_off_to": "lite_grounded_teaching",
    },
    {
        "office_id": "lite_grounded_teaching",
        "office_name": "lite_grounded_teaching",
        "role": "grounded_chat_teaching",
        "phase": "teaching",
        "responsibility": (
            "Turn local course evidence into one small teaching move, one learner "
            "question, and a safe next-step projection."
        ),
        "owns": [
            "student-facing explanation",
            "one-question pacing",
            "answer repair prompt",
            "next atom handoff",
        ],
        "required_tools": ["studio_teaching_chat_lesson_capsule"],
        "forbidden_responsibilities": [
            "formal queue writeback",
            "private diagnosis labels in student text",
            "full lesson dumping",
        ],
        "hands_off_to": "",
    },
)


def build_office_teaching_route_payload(
    *,
    node_id: str = "",
    scene_mode: str = "",
    user_intent: str = "",
) -> dict[str, Any]:
    normalized_node_id = str(node_id or "").strip()
    normalized_scene_mode = _normalize_scene_mode(str(scene_mode or ""))
    normalized_user_intent = str(user_intent or "").strip()
    requested_at = _utc_now_iso()
    chain = [dict(step) for step in _LITE_CHAIN]

    return {
        "status": "route_ready",
        "office_architecture_version": OFFICE_ARCHITECTURE_VERSION,
        "trace_kind": OFFICE_ROUTE_TRACE_KIND,
        "route_id": _stable_route_id(
            normalized_node_id,
            normalized_scene_mode,
            normalized_user_intent,
            requested_at,
        ),
        "requested_at": requested_at,
        "node_id": normalized_node_id,
        "scene_mode": normalized_scene_mode,
        "user_intent": normalized_user_intent,
        "frontdesk_contract": {
            "frontdesk_role": "public_web_learning_surface",
            "must_call_office_route_before_teaching": True,
            "must_respect_office_tool_ownership": True,
            "may_not_teach_directly": True,
            "student_visible_surface": "web_lite_frontdesk_only",
            "data_store_authority": "child_local_sqlite",
            "formal_writeback_allowed": False,
            "private_mother_state_allowed": False,
        },
        "route_policy": {
            "canonical_chain": [step["office_id"] for step in chain],
            "tool_calls_must_match_office_tool_ownership": True,
            "local_course_evidence_required": True,
            "web_frontdesk_is_public_demo_surface": True,
            "chat_events_are_local_projection_not_mastery": True,
            "queue_completion_requires_private_mother_project": False,
            "external_courseware_not_required_for_current_lesson": True,
            "student_safe_projection_only": True,
        },
        "office_tool_ownership": dict(_LITE_TOOL_OWNERSHIP),
        "office_chain": chain,
        "next_required_step": chain[0],
        "acceptance_markers": [
            OFFICE_ROUTE_TRACE_KIND,
            OFFICE_ARCHITECTURE_VERSION,
            OFFICE_TEACHING_ROUTE_TOOL,
            "child_local_sqlite",
            "lite_route_intake",
            "lite_state_projection",
            "lite_course_evidence",
            "lite_grounded_teaching",
            "studio_teaching_chat_lesson_capsule",
        ],
    }


def _normalize_scene_mode(scene_mode: str) -> str:
    return _SCENE_ALIASES.get(scene_mode.strip().lower(), scene_mode.strip().lower() or "learning")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _stable_route_id(node_id: str, scene_mode: str, user_intent: str, requested_at: str) -> str:
    seed = "\n".join([node_id, scene_mode, user_intent, requested_at])
    return f"lite_office_route_{sha1(seed.encode('utf-8')).hexdigest()[:16]}"
