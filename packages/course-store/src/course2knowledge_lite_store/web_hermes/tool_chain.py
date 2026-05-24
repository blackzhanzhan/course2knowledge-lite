from __future__ import annotations

from typing import Any

from course2knowledge_lite_store.office_route import build_office_teaching_route_payload


WEB_HERMES_TOOL_CHAIN_CONTRACT = "web_hermes_tool_chain_projection_contract"

_TOOL_LABELS = {
    "studio_office_teaching_route": "路由收缩",
    "studio_teaching_learning_companion_next": "学习队列",
    "studio_teaching_chat_lesson_capsule": "教学胶囊",
    "studio_teaching_state_get": "知识状态",
    "studio_teaching_evidence_list": "课程证据",
    "studio_teaching_context_get": "课程上下文",
}


def build_web_tool_chain_packet(
    *,
    user_intent: str,
    teaching_packet: dict[str, Any],
    course_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an internal mother-style route/tool trace for Web Hermes."""

    binding = dict(course_binding or {})
    route = build_office_teaching_route_payload(
        scene_mode="learning",
        user_intent=str(user_intent or "").strip(),
    )
    formal_bound = str(binding.get("binding_status") or "unbound") == "bound"
    companion_mode = "formal_single_course_companion" if formal_bound else "web_local_companion_projection"
    tool_steps = [
        _step(
            tool="studio_office_teaching_route",
            status="completed",
            student_label="路由收缩",
            detail="已按母项目门下路由规则收束到教学链路。",
        ),
        _step(
            tool="studio_teaching_learning_companion_next",
            status="projected" if not formal_bound else "completed",
            student_label="学习队列",
            detail=(
                "当前课程未绑定母项目正式队列，使用同构本地教学包。"
                if not formal_bound
                else "已按绑定课程范围选择下一口。"
            ),
        ),
        _step(
            tool="studio_teaching_chat_lesson_capsule",
            status="completed",
            student_label="教学胶囊",
            detail="已把课程证据收束成一个可回答的小问题。",
        ),
    ]
    return {
        "contract": WEB_HERMES_TOOL_CHAIN_CONTRACT,
        "status": "ready",
        "route_trace": route,
        "companion_mode": companion_mode,
        "tool_steps": tool_steps,
        "student_visible_steps": [
            {
                "label": step["student_label"],
                "status": step["status"],
                "detail": step["detail"],
            }
            for step in tool_steps
        ],
        "internal_rules": {
            "hide_route_ids": True,
            "hide_course_node_ids": True,
            "hide_queue_ids": True,
            "student_safe_projection_only": True,
            "formal_writeback_allowed": False,
        },
        "teaching_packet_contract": str(teaching_packet.get("contract") or ""),
    }


def tool_chain_prompt_context(packet: dict[str, Any]) -> str:
    steps = []
    for step in packet.get("tool_steps") or []:
        if not isinstance(step, dict):
            continue
        steps.append(
            f"- {step.get('tool', '')}: {step.get('status', '')}; student label: {step.get('student_label', '')}"
        )
    return "\n".join(
        [
            "Hermes tool-chain projection:",
            f"Contract: {packet.get('contract', '')}",
            f"Companion mode: {packet.get('companion_mode', '')}",
            "Steps:",
            "\n".join(steps),
            "Rule: follow this chain as if the mother frontdesk had routed the turn. Do not expose raw route, course, node, or queue identifiers.",
        ]
    )


def student_safe_tool_progress_from_gateway(payload: dict[str, Any]) -> dict[str, str]:
    tool = str(payload.get("tool") or "").strip()
    status = str(payload.get("status") or "").strip() or "running"
    return {
        "label": _TOOL_LABELS.get(tool, "Hermes 工具"),
        "status": "完成" if status == "completed" else "运行中",
        "detail": "Hermes 正在调用教学链路。" if status != "completed" else "Hermes 工具调用完成。",
    }


def _step(*, tool: str, status: str, student_label: str, detail: str) -> dict[str, str]:
    return {
        "tool": tool,
        "status": status,
        "student_label": student_label,
        "detail": detail,
    }
