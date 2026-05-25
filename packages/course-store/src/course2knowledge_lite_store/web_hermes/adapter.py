from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
import json
from time import perf_counter
from typing import Any, Iterator

from .gateway_client import HermesGatewayError, stream_hermes_gateway
from .teaching_convergence import (
    build_lite_teaching_convergence_state,
    teaching_convergence_prompt_context,
)
from .teaching_mode import build_web_teaching_mode_packet, teaching_packet_prompt_context
from .tool_chain import (
    build_web_tool_chain_packet,
    student_safe_tool_progress_from_gateway,
    tool_chain_prompt_context,
)


WEB_HERMES_FRONTDESK_CONTRACT = "web_hermes_frontdesk_channel_contract"
REQUIRED_TEACHING_ROUTE_TOOL = "studio_office_teaching_route"
_HIDDEN_FIELD_MARKERS = (
    "queue_id",
    "node_id",
    "course_id",
    "route_id",
    "record_id",
    "course_node_key",
    "selected_queue_id",
    "selected_node_id",
    "selected_course_id",
)


def build_web_hermes_turn(
    *,
    message: str,
    thread_id: str = "",
    channel: str = "web",
    course_hint: str = "",
    web_course_id: str = "",
    course_binding: dict[str, Any] | None = None,
    course_context: dict[str, Any] | None = None,
    chat_messages: list[dict[str, Any]] | None = None,
    chat_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a Web-safe teaching turn through the live Hermes gateway."""

    user_intent = " ".join(str(message or "").split())
    if not user_intent:
        raise ValueError("message is required")

    binding = dict(course_binding or {})
    teaching_packet = _build_controlled_teaching_packet(
        user_intent=user_intent,
        course_binding=binding,
        course_context=dict(course_context or {}),
        chat_messages=chat_messages,
        chat_events=chat_events,
    )
    tool_chain = build_web_tool_chain_packet(
        user_intent=user_intent,
        teaching_packet=teaching_packet,
        course_binding=binding,
    )
    thread = _thread_id(thread_id=thread_id, user_intent=user_intent)
    session_key = _session_key(channel=channel, web_course_id=web_course_id, thread_id=thread)
    system_prompt = _build_gateway_system_prompt(
        channel=channel,
        web_course_id=web_course_id,
        course_hint=course_hint,
        course_binding=binding,
        teaching_packet=teaching_packet,
        tool_chain=tool_chain,
        user_intent=user_intent,
    )
    gateway_message = _build_gateway_user_message(user_intent)

    try:
        collected_text: list[str] = []
        route_tool_completed = False
        route_retry_count = 0
        for attempt in range(2):
            collected_text = []
            buffered_deltas: list[str] = []
            route_tool_completed = False
            if attempt:
                route_retry_count += 1
            for item in stream_hermes_gateway(
                message=gateway_message,
                system_prompt=system_prompt,
                session_key=session_key,
                session_id=thread_id,
            ):
                item_type = str(item.get("type") or "")
                if item_type == "tool_progress":
                    payload = dict(item.get("payload") or {})
                    if _is_required_route_tool_completed(payload):
                        route_tool_completed = True
                        collected_text.extend(buffered_deltas)
                        buffered_deltas = []
                    continue
                if item_type == "delta":
                    delta = str(item.get("delta") or "")
                    if delta:
                        session_id = str(item.get("session_id") or "").strip()
                        if session_id:
                            thread = session_id
                        if route_tool_completed:
                            collected_text.append(delta)
                        else:
                            buffered_deltas.append(delta)
                elif item_type == "done":
                    session_id = str(item.get("session_id") or "").strip()
                    if session_id:
                        thread = session_id
            if route_tool_completed:
                break
        if route_tool_completed:
            visible = _gateway_visible_projection("".join(collected_text), teaching_packet=teaching_packet)
            status = "completed" if collected_text else "gateway_empty"
        else:
            visible = _required_route_tool_block_projection(teaching_packet=teaching_packet)
            status = "blocked_missing_required_route_tool"
        gateway_error = ""
    except HermesGatewayError as exc:
        visible = _gateway_error_projection(str(exc), teaching_packet=teaching_packet)
        status = "gateway_unavailable"
        gateway_error = str(exc)

    internal_trace = {
        "gateway_url": "HERMES_WEB_GATEWAY_URL",
        "gateway_status": status,
        "gateway_error": gateway_error,
        "web_course_ref": str(web_course_id or "").strip(),
        "course_binding_status": str(binding.get("binding_status") or "unbound"),
        "teaching_packet_contract": str(teaching_packet.get("contract") or ""),
        "route_retry_count": route_retry_count if "route_retry_count" in locals() else 0,
    }
    return {
        "status": status,
        "contract": WEB_HERMES_FRONTDESK_CONTRACT,
        "thread_id": thread,
        "channel": str(channel or "web").strip() or "web",
        "student_visible": visible,
        "internal_trace": internal_trace,
        "teaching_packet": teaching_packet,
        "tool_chain": tool_chain,
    }


def stream_web_hermes_sse_events(
    *,
    message: str,
    thread_id: str = "",
    channel: str = "web",
    course_hint: str = "",
    web_course_id: str = "",
    course_binding: dict[str, Any] | None = None,
    course_context: dict[str, Any] | None = None,
    chat_messages: list[dict[str, Any]] | None = None,
    chat_events: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield Web-safe SSE events while the live Hermes gateway streams."""

    user_intent = " ".join(str(message or "").split())
    if not user_intent:
        raise ValueError("message is required")

    binding = dict(course_binding or {})
    teaching_packet = _build_controlled_teaching_packet(
        user_intent=user_intent,
        course_binding=binding,
        course_context=dict(course_context or {}),
        chat_messages=chat_messages,
        chat_events=chat_events,
    )
    tool_chain = build_web_tool_chain_packet(
        user_intent=user_intent,
        teaching_packet=teaching_packet,
        course_binding=binding,
    )
    thread = _thread_id(thread_id=thread_id, user_intent=user_intent)
    session_key = _session_key(channel=channel, web_course_id=web_course_id, thread_id=thread)
    system_prompt = _build_gateway_system_prompt(
        channel=channel,
        web_course_id=web_course_id,
        course_hint=course_hint,
        course_binding=binding,
        teaching_packet=teaching_packet,
        tool_chain=tool_chain,
        user_intent=user_intent,
    )
    gateway_message = _build_gateway_user_message(user_intent)

    started_at = perf_counter()
    route_completed_at = 0.0
    first_delta_at = 0.0
    yield _assert_student_safe_event(_route_ready_event())
    yield _assert_student_safe_event(_teaching_state_event(teaching_packet, status="live_gateway"))
    yield _assert_student_safe_event(
        _runtime_metric_event(
            stage="gateway_request_ready",
            started_at=started_at,
            system_prompt=system_prompt,
            teaching_packet=teaching_packet,
            tool_chain=tool_chain,
        )
    )

    status = "completed"
    had_released_text = False
    route_tool_completed = False
    buffered_deltas: list[str] = []
    try:
        for attempt in range(2):
            route_tool_completed = False
            buffered_deltas = []
            if attempt:
                yield _assert_student_safe_event(
                    _tool_chain_event({"label": "路由收缩", "status": "running", "detail": "正在重新走教学路由。"})
                )
            for item in stream_hermes_gateway(
                message=gateway_message,
                system_prompt=system_prompt,
                session_key=session_key,
                session_id=thread_id,
            ):
                item_type = str(item.get("type") or "")
                if item_type == "tool_progress":
                    payload = dict(item.get("payload") or {})
                    yield _assert_student_safe_event(_tool_chain_event(student_safe_tool_progress_from_gateway(payload)))
                    if _is_required_route_tool_completed(payload):
                        if not route_completed_at:
                            route_completed_at = perf_counter()
                            yield _assert_student_safe_event(
                                _runtime_metric_event(
                                    stage="route_tool_completed",
                                    started_at=started_at,
                                    route_completed_at=route_completed_at,
                                    system_prompt=system_prompt,
                                    teaching_packet=teaching_packet,
                                    tool_chain=tool_chain,
                                )
                            )
                        route_tool_completed = True
                        for buffered_delta in buffered_deltas:
                            if not first_delta_at:
                                first_delta_at = perf_counter()
                            yield _assert_student_safe_event(
                                _event(
                                    "message_delta",
                                    {
                                        "delta": buffered_delta,
                                        "source": "live_hermes_gateway",
                                        "must_wait_for_student_answer": True,
                                    },
                                )
                            )
                            had_released_text = True
                        buffered_deltas = []
                    continue
                if item_type == "delta":
                    delta = str(item.get("delta") or "")
                    if delta:
                        session_id = str(item.get("session_id") or "").strip()
                        if session_id:
                            thread = session_id
                        if not route_tool_completed:
                            buffered_deltas.append(delta)
                            continue
                        if not first_delta_at:
                            first_delta_at = perf_counter()
                            yield _assert_student_safe_event(
                                _runtime_metric_event(
                                    stage="first_visible_delta",
                                    started_at=started_at,
                                    route_completed_at=route_completed_at,
                                    first_delta_at=first_delta_at,
                                    system_prompt=system_prompt,
                                    teaching_packet=teaching_packet,
                                    tool_chain=tool_chain,
                                )
                            )
                        yield _assert_student_safe_event(
                            _event(
                                "message_delta",
                                {
                                    "delta": delta,
                                    "source": "live_hermes_gateway",
                                    "must_wait_for_student_answer": True,
                                },
                            )
                        )
                        had_released_text = True
                elif item_type == "done":
                    session_id = str(item.get("session_id") or "").strip()
                    if session_id:
                        thread = session_id
            if route_tool_completed:
                break
    except HermesGatewayError as exc:
        status = "gateway_unavailable"
        yield _assert_student_safe_event(
            _event(
                "error",
                {
                    "reason": "hermes_gateway_unavailable",
                    "message": _gateway_error_projection(str(exc), teaching_packet=teaching_packet)[
                        "fallback_message"
                    ],
                },
            )
        )

    if status == "completed" and not route_tool_completed:
        status = "blocked_missing_required_route_tool"
        yield _assert_student_safe_event(
            _event(
                "error",
                {
                    "reason": "teaching_route_not_ready",
                    "message": "本轮教学路由没有完成，我已经拦下这次回复。请再发送一次，我会重新走教学路由。",
                },
            )
        )
    elif status == "completed" and not had_released_text:
        status = "gateway_empty"
        yield _assert_student_safe_event(
            _event(
                "error",
                {
                    "reason": "hermes_gateway_empty",
                    "message": "Hermes gateway did not return a visible reply.",
                },
            )
        )
    yield _assert_student_safe_event(
        _runtime_metric_event(
            stage="stream_done",
            started_at=started_at,
            route_completed_at=route_completed_at,
            first_delta_at=first_delta_at,
            system_prompt=system_prompt,
            teaching_packet=teaching_packet,
            tool_chain=tool_chain,
        )
    )
    yield _assert_student_safe_event(_event("done", {"status": status}))
    yield _assert_student_safe_event(_thread_state_event(thread_id=thread, channel=channel, status=status))


def build_web_hermes_sse_events(turn: dict[str, Any]) -> list[dict[str, Any]]:
    visible = dict(turn.get("student_visible") or {})
    atoms = list(visible.get("knowledge_atoms") or [])
    status = str(turn.get("status") or "gateway_unavailable")
    events: list[dict[str, Any]] = [
        _route_ready_event(),
        _event(
            "teaching_state",
            {
                "status": visible.get("teaching_status", status),
                "progress_ratio_label": visible.get("progress_ratio_label", ""),
                "next_step_label": visible.get("next_step_label", ""),
                "knowledge_atoms": atoms,
            },
        ),
    ]
    message = str(visible.get("message") or "").strip()
    if message:
        events.append(
            _event(
                "message_delta",
                {
                    "delta": message,
                    "source": "live_hermes_gateway",
                    "must_wait_for_student_answer": True,
                },
            )
        )
    else:
        events.append(
            _event(
                "error",
                {
                    "reason": "hermes_gateway_unavailable",
                    "message": str(visible.get("fallback_message") or "Hermes gateway is not available."),
                },
            )
        )
    events.append(_event("done", {"status": status}))
    events.append(
        _thread_state_event(
            thread_id=str(turn.get("thread_id") or ""),
            channel=str(turn.get("channel") or "web"),
            status=status,
        )
    )
    return [_assert_student_safe_event(event) for event in events]


def _build_controlled_teaching_packet(
    *,
    user_intent: str,
    course_binding: dict[str, Any],
    course_context: dict[str, Any],
    chat_messages: list[dict[str, Any]] | None = None,
    chat_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    preliminary = build_web_teaching_mode_packet(
        user_intent=user_intent,
        course_binding=course_binding,
        course_context=course_context,
    )
    visible_state = dict(preliminary.get("student_visible_state") or {})
    atoms = list(visible_state.get("knowledge_atoms") or [])
    teaching_control = build_lite_teaching_convergence_state(
        knowledge_atoms=atoms,
        chat_messages=chat_messages,
        chat_events=chat_events,
    )
    return build_web_teaching_mode_packet(
        user_intent=user_intent,
        course_binding=course_binding,
        course_context=course_context,
        teaching_control=teaching_control,
    )


def _gateway_visible_projection(message: str, *, teaching_packet: dict[str, Any]) -> dict[str, Any]:
    text = str(message or "").strip()
    state = dict(teaching_packet.get("student_visible_state") or {})
    return {
        "turn_status": "completed" if text else "blocked",
        "message": text,
        "fallback_message": "",
        "teaching_status": "live_gateway",
        "progress_ratio_label": state.get("progress_ratio_label", ""),
        "momentum_line": "",
        "next_step_label": state.get("next_step_label", "teaching"),
        "knowledge_atoms": list(state.get("knowledge_atoms") or []),
    }


def _gateway_error_projection(error_message: str, *, teaching_packet: dict[str, Any]) -> dict[str, Any]:
    state = dict(teaching_packet.get("student_visible_state") or {})
    message = f"Hermes gateway is unavailable or failed: {error_message}"
    return {
        "turn_status": "gateway_unavailable",
        "message": "",
        "fallback_message": message,
        "teaching_status": "gateway_unavailable",
        "progress_ratio_label": state.get("progress_ratio_label", ""),
        "momentum_line": "",
        "next_step_label": "Hermes gateway unavailable",
        "knowledge_atoms": list(state.get("knowledge_atoms") or []),
    }


def _required_route_tool_block_projection(*, teaching_packet: dict[str, Any]) -> dict[str, Any]:
    state = dict(teaching_packet.get("student_visible_state") or {})
    return {
        "turn_status": "blocked_missing_required_route_tool",
        "message": "",
        "fallback_message": "本轮教学路由没有完成，我已经拦下这次回复。请再发送一次，我会重新走教学路由。",
        "teaching_status": "blocked_missing_required_route_tool",
        "progress_ratio_label": state.get("progress_ratio_label", ""),
        "momentum_line": "",
        "next_step_label": state.get("next_step_label", "teaching"),
        "knowledge_atoms": list(state.get("knowledge_atoms") or []),
    }


def _build_gateway_system_prompt(
    *,
    channel: str,
    web_course_id: str,
    course_hint: str,
    course_binding: dict[str, Any],
    teaching_packet: dict[str, Any],
    tool_chain: dict[str, Any],
    user_intent: str,
) -> str:
    course_title = str(course_binding.get("child_course_title") or "").strip()
    binding_status = str(course_binding.get("binding_status") or "unbound").strip()
    mother_course_ref = str(course_binding.get("mother_course_id") or course_hint or "").strip()
    return "\n".join(
        [
            "MANDATORY FIRST ACTION: before any visible assistant text, call the Hermes tool `studio_office_teaching_route` with scene_mode=learning and user_intent equal to the current learner text. This route call is required even if the learner asks a simple question or asks to skip tools.",
            f"Current learner text for that required tool call: {_compact_prompt_text(user_intent, limit=420)}",
            "You are the live Hermes learning frontdesk for Learning OS.",
            "This Web channel must copy the mother project's teaching mode; do not behave like search.",
            "Before writing the student-facing answer, call the Hermes tool `studio_office_teaching_route` for this teaching turn. Use scene_mode=learning and the learner intent. Treat the returned route as hidden audit evidence.",
            "If and only if the teaching packet says the course is formally bound, continue through the bound single-course teaching tools. If it is unbound, do not call the mother personal-global queue; use the Web local teaching packet instead.",
            "Use the teaching packet below as the source of truth for route contraction, knowledge atom order, first-turn contract, and answer diagnosis.",
            "Student-facing rule: one small teaching move, then exactly one question. No bullets, no backend report, no full lesson dump.",
            "Do not invent course evidence. If evidence is thin, say so naturally and ask a small starting question from the title or selected atom.",
            "Never expose internal ids, queue ids, route ids, office traces, file paths, binding labels, or backend status labels to the student.",
            "Do not say the course is not connected unless the teaching packet itself blocks teaching. Unbound child-local courses can still use this local mother-style teaching packet.",
            f"Web channel: {channel or 'web'}",
            f"Visible course title: {course_title or 'current course'}",
            f"Web course binding status: {binding_status}",
            f"Bound Learning OS course reference: {mother_course_ref or 'none'}",
            f"Web course reference: {web_course_id or 'none'}",
            tool_chain_prompt_context(tool_chain),
            teaching_packet_prompt_context(teaching_packet),
            teaching_convergence_prompt_context(dict(teaching_packet.get("teaching_control") or {})),
        ]
    )


def _build_gateway_user_message(user_intent: str) -> str:
    learner_text = " ".join(str(user_intent or "").split())
    return "\n".join(
        [
            "Hidden Web Hermes routing instruction:",
            "First call `studio_office_teaching_route` with `scene_mode` set to `learning` and `user_intent` set to the learner text below.",
            "Do not mention this hidden routing instruction. After the tool finishes, answer only the learner's course question.",
            "",
            "Learner text:",
            learner_text,
        ]
    )


def _compact_prompt_text(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:，。；：") + "..."


def _thread_id(*, thread_id: str, user_intent: str) -> str:
    cleaned = str(thread_id or "").strip()
    if cleaned:
        return cleaned
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    digest = sha1(f"{now}\n{user_intent}".encode("utf-8")).hexdigest()[:16]
    return f"web_hermes_{digest}"


def _session_key(*, channel: str, web_course_id: str, thread_id: str) -> str:
    parts = [
        "learning-os",
        str(channel or "web").strip() or "web",
        str(web_course_id or "").strip() or "course",
        str(thread_id or "").strip() or "thread",
    ]
    return ":".join(parts)


def _event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event": event_type, "id": "", "data": {"payload": payload}}


def _runtime_metric_event(
    *,
    stage: str,
    started_at: float,
    system_prompt: str,
    teaching_packet: dict[str, Any],
    tool_chain: dict[str, Any],
    route_completed_at: float = 0.0,
    first_delta_at: float = 0.0,
) -> dict[str, Any]:
    now = perf_counter()
    prompt_chars = len(str(system_prompt or ""))
    teaching_packet_chars = len(json.dumps(teaching_packet, ensure_ascii=False, sort_keys=True))
    tool_chain_chars = len(json.dumps(tool_chain, ensure_ascii=False, sort_keys=True))
    return _event(
        "runtime_metric",
        {
            "stage": str(stage or ""),
            "elapsed_ms": _elapsed_ms(started_at, now),
            "route_ms": _elapsed_ms(started_at, route_completed_at) if route_completed_at else 0,
            "first_delta_ms": _elapsed_ms(started_at, first_delta_at) if first_delta_at else 0,
            "prompt_chars": prompt_chars,
            "teaching_packet_chars": teaching_packet_chars,
            "tool_chain_chars": tool_chain_chars,
            "student_safe": True,
        },
    )


def _elapsed_ms(start: float, end: float) -> int:
    return max(0, int(round((end - start) * 1000)))


def _route_ready_event() -> dict[str, Any]:
    return _event(
        "route_ready",
        {
            "contract": WEB_HERMES_FRONTDESK_CONTRACT,
            "route": "live_hermes_gateway",
            "student_surface": "web_frontdesk",
            "internal_trace_hidden": True,
        },
    )


def _teaching_state_event(teaching_packet: dict[str, Any], *, status: str) -> dict[str, Any]:
    state = dict(teaching_packet.get("student_visible_state") or {})
    control = _student_safe_teaching_control(teaching_packet)
    gate = _student_safe_learning_signals(teaching_packet)
    return _event(
        "teaching_state",
        {
            "status": status,
            "progress_ratio_label": state.get("progress_ratio_label", ""),
            "next_step_label": state.get("next_step_label", "teaching"),
            "knowledge_atoms": list(state.get("knowledge_atoms") or []),
            "teaching_control": control,
            "learning_signals": gate,
        },
    )


def _student_safe_teaching_control(teaching_packet: dict[str, Any]) -> dict[str, Any]:
    control = dict(teaching_packet.get("teaching_control") or {})
    visible = dict(control.get("student_visible") or {})
    return {
        "contract": str(control.get("contract") or ""),
        "position_index": int(control.get("current_atom_index") or 0),
        "passed_count": int(control.get("completed_atom_count") or 0),
        "total_count": int(control.get("total_atom_count") or 0),
        "next_step_label": str(visible.get("next_step_label") or ""),
    }


def _student_safe_learning_signals(teaching_packet: dict[str, Any]) -> dict[str, Any]:
    control = dict(teaching_packet.get("teaching_control") or {})
    gate = dict(control.get("mastery_gate") or {})
    return {
        "retrieval_signal": bool(gate.get("retrieval_signal")),
        "grounded_evidence_signal": bool(gate.get("grounded_evidence_signal")),
        "causal_chain_signal": bool(gate.get("causal_chain_signal")),
        "boundary_signal": bool(gate.get("boundary_signal")),
        "transfer_signal": bool(gate.get("transfer_signal")),
        "scope_challenge_signal": bool(gate.get("scope_challenge_signal")),
        "same_atom_probe_count": int(gate.get("same_atom_probe_count") or 0),
        "overquestioning_risk": bool(gate.get("overquestioning_risk")),
    }


def _tool_chain_event(step: dict[str, Any]) -> dict[str, Any]:
    return _event(
        "tool_chain",
        {
            "label": str(step.get("label") or step.get("student_label") or "Hermes 工具链"),
            "status": _student_safe_status(str(step.get("status") or "running")),
            "detail": str(step.get("detail") or ""),
        },
    )


def _student_safe_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"completed", "complete", "done"}:
        return "完成"
    if normalized in {"projected", "ready"}:
        return "已收束"
    if normalized in {"running", "started"}:
        return "运行中"
    return status or "运行中"


def _is_required_route_tool_completed(payload: dict[str, Any]) -> bool:
    tool = str(payload.get("tool") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    return tool == REQUIRED_TEACHING_ROUTE_TOOL and status in {"completed", "complete", "done"}


def _thread_state_event(*, thread_id: str, channel: str, status: str) -> dict[str, Any]:
    return {
        "event": "thread_state",
        "id": str(thread_id or ""),
        "data": {
            "status": status,
            "route": "hermes_frontdesk",
            "thread": {
                "thread_id": str(thread_id or ""),
                "channel": str(channel or "web"),
            },
        },
    }


def _assert_student_safe_event(event: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(event, ensure_ascii=False)
    lower = serialized.lower()
    leaked = [marker for marker in _HIDDEN_FIELD_MARKERS if marker in lower]
    if leaked:
        raise ValueError(f"student-visible Web Hermes event leaked hidden fields: {', '.join(leaked)}")
    return event
