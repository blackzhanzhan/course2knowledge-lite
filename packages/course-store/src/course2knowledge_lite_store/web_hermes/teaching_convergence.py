from __future__ import annotations

import re
from typing import Any


LITE_TEACHING_CONVERGENCE_CONTRACT = "lite_teaching_convergence_contract"
LITE_CHAT_MASTERY_GATE_CONTRACT = "lite_chat_mastery_gate_contract"

_RAG_AGENT_TERMS = ("rag", "agent")
_LOW_FOUNDATION_TERMS = ("不知道", "不清楚", "不太清楚", "不懂", "不会", "没听懂")
_SCOPE_CHALLENGE_TERMS = (
    "哪个层面",
    "什么层面",
    "需求场景",
    "场景没有",
    "没有表述清楚",
    "过度设计",
    "写个论文",
    "展开来讲",
    "你是要",
    "边界不清",
)
_RETRIEVAL_TERMS = (
    "核心",
    "关键",
    "先",
    "再",
    "然后",
    "最后",
    "本质",
    "判断",
    "回答",
    "理解",
    "变成",
    "retrieve",
    "recall",
)
_EVIDENCE_TERMS = (
    "视频",
    "课程",
    "字幕",
    "片段",
    "文段",
    "材料",
    "上下文",
    "证据",
    "引用",
    "标题",
    "正文",
    "markdown",
    "md",
    "检索",
    "向量",
    "topk",
    "rag",
    "数据库",
    "知识库",
    "embedding",
    "embanding",
)
_CAUSAL_TERMS = (
    "因为",
    "所以",
    "导致",
    "让",
    "为了",
    "原因",
    "提高",
    "降低",
    "解决",
    "避免",
    "服务",
    "依赖",
    "利于",
    "方便",
    "干扰",
    "准确",
    "纯净",
    "区分",
)
_BOUNDARY_TERMS = (
    "不是",
    "而是",
    "不能",
    "不要",
    "区别",
    "边界",
    "场景",
    "条件",
    "如果",
    "适合",
    "不适合",
    "相比",
    "取决",
    "够用",
    "过度设计",
    "重合",
    "替代",
)
_TRANSFER_TERMS = (
    "如果",
    "场景",
    "面试",
    "可以",
    "适合",
    "当",
    "换成",
    "小体量",
    "数据量",
    "动态更新",
    "扩展",
    "算法",
    "搜索树",
    "聚类",
    "维护",
    "应用",
    "举例",
    "markdown",
    "md",
    "rag",
    "向量化",
    "检索树",
)
_CORRECTION_TERMS = ("改", "补", "修正", "换句话", "我认为", "应该", "更准确", "确实")
_PROBE_TERMS = ("再", "补", "一句", "为什么", "怎么", "哪", "能", "试着", "收口", "关键")


def build_lite_teaching_convergence_state(
    *,
    knowledge_atoms: list[dict[str, Any]],
    chat_messages: list[dict[str, Any]] | None = None,
    chat_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Infer child-local teaching convergence from public chat history.

    This is deliberately not mother mastery state. It copies the mother
    mastery-gate shape into a child-local Web control layer so the live model can
    stop looping after the learner has supplied enough evidence.
    """

    atoms = [_normalize_atom(atom, index) for index, atom in enumerate(knowledge_atoms or [])]
    messages = [dict(item) for item in (chat_messages or []) if isinstance(item, dict)]
    prior = _latest_teaching_control(chat_events or [])
    user_answers = [
        str(message.get("content") or "").strip()
        for message in messages
        if str(message.get("role") or "").strip() == "user" and str(message.get("content") or "").strip()
    ]
    assistant_turns = [
        str(message.get("content") or "").strip()
        for message in messages
        if str(message.get("role") or "").strip() == "assistant" and str(message.get("content") or "").strip()
    ]
    gate = _evaluate_lite_chat_mastery_gate(
        user_answers=user_answers,
        assistant_turns=assistant_turns,
        atoms=atoms,
        prior=prior,
    )
    diagnosis = {"label": str(gate.get("diagnosis_label") or ""), "summary": str(gate.get("answer_summary") or "")}
    prior_index = _coerce_index(prior.get("current_atom_index", prior.get("position_index")), len(atoms))
    current_index = prior_index
    just_advanced = False
    passed_current = False
    if _gate_allows_advancement(gate) and atoms:
        if prior_index < len(atoms) - 1:
            current_index = prior_index + 1
            just_advanced = True
        else:
            passed_current = True
    statuses = _atom_statuses(
        atoms=atoms,
        current_index=current_index,
        diagnosis_label=diagnosis["label"],
        current_passed=passed_current,
    )
    next_action = _next_action(
        diagnosis["label"],
        gate=gate,
        atoms=atoms,
        current_index=current_index,
        just_advanced=just_advanced,
        passed_current=passed_current,
    )
    completed_count = sum(1 for item in statuses if item.get("teaching_status") == "passed")

    return {
        "contract": LITE_TEACHING_CONVERGENCE_CONTRACT,
        "authority": {
            "source": "child_local_chat_history",
            "writes_mother_learning_state": False,
            "writes_queue_completion": False,
            "student_safe_projection_only": True,
        },
        "current_atom_index": current_index if atoms else 0,
        "completed_atom_count": completed_count,
        "total_atom_count": len(atoms),
        "progress_ratio_label": f"{min(completed_count + 1, len(atoms))}/{len(atoms)}" if atoms else "",
        "latest_diagnosis_label": diagnosis["label"],
        "latest_student_answer_summary": diagnosis["summary"],
        "mastery_gate": gate,
        "next_action": next_action,
        "atom_statuses": statuses,
        "prompt_rules": _prompt_rules(
            next_action=next_action,
            diagnosis=diagnosis,
            gate=gate,
            atoms=atoms,
            current_index=current_index,
        ),
        "student_visible": {
            "next_step_label": _student_next_step(next_action),
            "knowledge_atoms": _student_atoms(statuses),
            "learning_signals": _student_learning_signals(gate),
        },
    }


def teaching_convergence_prompt_context(state: dict[str, Any]) -> str:
    rules = list(state.get("prompt_rules") or [])
    gate = dict(state.get("mastery_gate") or {})
    atoms = list((state.get("student_visible") or {}).get("knowledge_atoms") or [])
    lines = [
        "Lite teaching convergence state:",
        f"Contract: {state.get('contract', '')}",
        f"Current atom position: {state.get('progress_ratio_label', '')}",
        f"Hidden mastery label: {state.get('latest_diagnosis_label', '')}",
        f"Next action: {state.get('next_action', '')}",
        "Mastery-gate signals:",
        f"- retrieval={bool(gate.get('retrieval_signal'))}; evidence={bool(gate.get('grounded_evidence_signal'))}; causal={bool(gate.get('causal_chain_signal'))}; boundary={bool(gate.get('boundary_signal'))}; transfer={bool(gate.get('transfer_signal'))}",
        f"- repeated_probe_count={int(gate.get('same_atom_probe_count') or 0)}; overquestioning_risk={bool(gate.get('overquestioning_risk'))}; scope_challenge={bool(gate.get('scope_challenge_signal'))}",
        "Hard rules:",
    ]
    lines.extend(f"- {rule}" for rule in rules[:8])
    lines.append("Student-safe atom status:")
    for atom in atoms[:8]:
        lines.append(
            "- "
            + " | ".join(
                part
                for part in (
                    str(atom.get("label") or ""),
                    str(atom.get("status") or ""),
                    str(atom.get("focus") or ""),
                )
                if part
            )
        )
    return "\n".join(lines)


def _evaluate_lite_chat_mastery_gate(
    *,
    user_answers: list[str],
    assistant_turns: list[str],
    atoms: list[dict[str, Any]],
    prior: dict[str, Any],
) -> dict[str, Any]:
    if not user_answers:
        return _gate_payload(
            diagnosis_label="needs_first_answer",
            user_answers=user_answers,
            assistant_turns=assistant_turns,
            metrics={},
            missing=("retrieval",),
            answer_summary="",
        )

    latest_raw = user_answers[-1]
    latest = _normalize_text(latest_raw)
    recent = _normalize_text(" ".join(user_answers[-5:]))
    assistant_recent = _normalize_text(" ".join(assistant_turns[-5:]))
    atom_hits = _atom_hit_count(recent, atoms)
    same_atom_probe_count = _same_atom_probe_count(assistant_turns)
    scope_challenge_signal = _contains_any(recent, _SCOPE_CHALLENGE_TERMS)
    low_foundation_signal = (
        _contains_any(latest, _LOW_FOUNDATION_TERMS)
        and len(latest) < 34
        and not _contains_any(latest, _CAUSAL_TERMS + _BOUNDARY_TERMS)
    )
    retrieval_signal = len(latest) >= 10 or _contains_any(recent, _RETRIEVAL_TERMS) or len(user_answers) >= 2
    grounded_evidence_signal = atom_hits > 0 or _contains_any(recent, _EVIDENCE_TERMS)
    causal_chain_signal = _contains_any(recent, _CAUSAL_TERMS)
    boundary_signal = _contains_any(recent, _BOUNDARY_TERMS) or _is_rag_agent_boundary_answer(recent, atoms)
    transfer_signal = _contains_any(recent, _TRANSFER_TERMS) and (len(latest) >= 18 or len(recent) >= 80)
    correction_completed = _contains_any(latest, _CORRECTION_TERMS) and (
        causal_chain_signal or boundary_signal or grounded_evidence_signal
    )
    evidence_count = sum(
        1
        for value in (
            retrieval_signal,
            grounded_evidence_signal,
            causal_chain_signal,
            boundary_signal,
            transfer_signal,
        )
        if value
    )
    overquestioning_risk = same_atom_probe_count >= 2 and evidence_count >= 3
    exit_check_passed = (
        evidence_count >= 4
        and retrieval_signal
        and grounded_evidence_signal
        and (causal_chain_signal or boundary_signal)
    ) or overquestioning_risk
    if scope_challenge_signal and evidence_count >= 2:
        exit_check_passed = True

    metrics = {
        "retrieval_signal": retrieval_signal,
        "grounded_evidence_signal": grounded_evidence_signal,
        "causal_chain_signal": causal_chain_signal,
        "boundary_signal": boundary_signal,
        "transfer_signal": transfer_signal,
        "correction_completed": correction_completed,
        "exit_check_passed": exit_check_passed,
        "scope_challenge_signal": scope_challenge_signal,
        "same_atom_probe_count": same_atom_probe_count,
        "overquestioning_risk": overquestioning_risk,
        "atom_hit_count": atom_hits,
    }

    missing = _missing_metric_names(metrics)
    if low_foundation_signal:
        label = "low_foundation_blank"
    elif scope_challenge_signal and exit_check_passed:
        label = "scope_challenge_ready"
    elif exit_check_passed and evidence_count >= 4:
        label = "transfer_ready"
    elif evidence_count >= 3:
        label = "solid_paraphrase"
    elif retrieval_signal and grounded_evidence_signal and not causal_chain_signal:
        label = "fluent_missing_causal_chain"
    elif retrieval_signal and causal_chain_signal and not boundary_signal and _asks_for_boundary(assistant_recent):
        label = "boundary_confusion"
    else:
        label = "surface_terms_only"

    shallow = label in {"surface_terms_only", "solid_paraphrase"} and not exit_check_passed
    pseudo_mastery_unresolved = label in {
        "surface_terms_only",
        "fluent_missing_causal_chain",
        "boundary_confusion",
    }
    return _gate_payload(
        diagnosis_label=label,
        user_answers=user_answers,
        assistant_turns=assistant_turns,
        metrics={
            **metrics,
            "low_foundation_unresolved": label == "low_foundation_blank",
            "pseudo_mastery_unresolved": pseudo_mastery_unresolved,
            "missing_causal_chain_unresolved": "causal_chain" in missing,
            "boundary_confusion_unresolved": label == "boundary_confusion",
            "one_micro_step_only": shallow and len(user_answers) <= 1,
            "multi_turn_dialogue": len(user_answers) >= 2 or len(assistant_turns) >= 2,
            "course_evidence_used": grounded_evidence_signal,
            "grounded_explanation_given": grounded_evidence_signal,
            "learner_response_collected": True,
            "response_diagnosed": True,
        },
        missing=missing,
        answer_summary=_compact(latest_raw, limit=140),
        prior=prior,
    )


def _gate_payload(
    *,
    diagnosis_label: str,
    user_answers: list[str],
    assistant_turns: list[str],
    metrics: dict[str, Any],
    missing: tuple[str, ...],
    answer_summary: str,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "contract": LITE_CHAT_MASTERY_GATE_CONTRACT,
        "course_evidence_used": bool(metrics.get("course_evidence_used", metrics.get("grounded_evidence_signal"))),
        "grounded_explanation_given": bool(
            metrics.get("grounded_explanation_given", metrics.get("grounded_evidence_signal"))
        ),
        "learner_response_collected": bool(metrics.get("learner_response_collected", bool(user_answers))),
        "response_diagnosed": bool(metrics.get("response_diagnosed", bool(user_answers))),
        "multi_turn_dialogue": bool(metrics.get("multi_turn_dialogue", len(user_answers) >= 2 or len(assistant_turns) >= 2)),
        "exit_check_passed": bool(metrics.get("exit_check_passed")),
        "correction_completed": bool(metrics.get("correction_completed")),
        "one_correct_choice_only": False,
        "one_confirmation_only": False,
        "one_micro_step_only": bool(metrics.get("one_micro_step_only")),
        "diagnosis_label": diagnosis_label,
        "pseudo_mastery_unresolved": bool(metrics.get("pseudo_mastery_unresolved")),
        "low_foundation_unresolved": bool(metrics.get("low_foundation_unresolved")),
        "missing_causal_chain_unresolved": bool(metrics.get("missing_causal_chain_unresolved")),
        "boundary_confusion_unresolved": bool(metrics.get("boundary_confusion_unresolved")),
        "retrieval_signal": bool(metrics.get("retrieval_signal")),
        "grounded_evidence_signal": bool(metrics.get("grounded_evidence_signal")),
        "causal_chain_signal": bool(metrics.get("causal_chain_signal")),
        "boundary_signal": bool(metrics.get("boundary_signal")),
        "transfer_signal": bool(metrics.get("transfer_signal")),
        "scope_challenge_signal": bool(metrics.get("scope_challenge_signal")),
        "same_atom_probe_count": int(metrics.get("same_atom_probe_count") or 0),
        "overquestioning_risk": bool(metrics.get("overquestioning_risk")),
        "atom_hit_count": int(metrics.get("atom_hit_count") or 0),
        "missing_signals": list(missing),
        "answer_summary": answer_summary,
        "prior_gate_seen": bool(prior),
    }
    payload["passed"] = _gate_allows_advancement(payload)
    return payload


def _missing_metric_names(metrics: dict[str, Any]) -> tuple[str, ...]:
    missing = []
    if not metrics.get("retrieval_signal"):
        missing.append("retrieval")
    if not metrics.get("grounded_evidence_signal"):
        missing.append("evidence")
    if not metrics.get("causal_chain_signal"):
        missing.append("causal_chain")
    if not metrics.get("boundary_signal"):
        missing.append("boundary")
    if not metrics.get("transfer_signal") and not metrics.get("exit_check_passed"):
        missing.append("transfer")
    return tuple(missing)


def _gate_allows_advancement(gate: dict[str, Any]) -> bool:
    label = str(gate.get("diagnosis_label") or "")
    if label in {"transfer_ready", "scope_challenge_ready"}:
        return True
    return bool(gate.get("exit_check_passed")) and not any(
        bool(gate.get(flag))
        for flag in (
            "pseudo_mastery_unresolved",
            "low_foundation_unresolved",
            "missing_causal_chain_unresolved",
            "boundary_confusion_unresolved",
            "one_micro_step_only",
        )
    )


def _normalize_atom(atom: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "label": _compact(atom.get("label") or atom.get("title") or f"知识点 {index + 1}", limit=72),
        "focus": _compact(atom.get("focus") or atom.get("summary") or atom.get("body") or "", limit=120),
        "atom_type": _compact(atom.get("atom_type") or "concept", limit=24),
        "review_question": _compact(atom.get("review_question") or _first(atom.get("review_questions")), limit=120),
        "confidence": _compact(atom.get("confidence") or "", limit=24),
    }


def _latest_teaching_control(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed([dict(item) for item in events if isinstance(item, dict)]):
        if str(event.get("event_type") or "") != "teaching_control":
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            if isinstance(payload.get("payload"), dict):
                return dict(payload.get("payload") or {})
            return dict(payload)
    return {}


def _atom_statuses(
    *,
    atoms: list[dict[str, Any]],
    current_index: int,
    diagnosis_label: str,
    current_passed: bool = False,
) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for atom in atoms:
        index = int(atom["index"])
        if index < current_index or (current_passed and index == current_index):
            teaching_status = "passed"
            label = "已通过"
        elif index == current_index:
            teaching_status = "exit_check" if diagnosis_label == "solid_paraphrase" else "current"
            label = "收口确认" if teaching_status == "exit_check" else "当前口"
        else:
            teaching_status = "waiting"
            label = "候选"
        statuses.append({**atom, "teaching_status": teaching_status, "status": label})
    return statuses


def _next_action(
    label: str,
    *,
    gate: dict[str, Any],
    atoms: list[dict[str, Any]],
    current_index: int,
    just_advanced: bool = False,
    passed_current: bool = False,
) -> str:
    if label == "scope_challenge_ready":
        return "set_scope_and_advance" if just_advanced else "set_scope_and_close"
    if label == "transfer_ready" or passed_current:
        if just_advanced:
            return "advance_to_next_atom"
        return "lesson_bite_complete"
    if label == "solid_paraphrase":
        if bool(gate.get("overquestioning_risk")):
            return "advance_to_next_atom" if current_index < len(atoms) - 1 else "lesson_bite_complete"
        return "ask_exit_check"
    if label in {"needs_first_answer", "low_foundation_blank"}:
        return "shrink_and_reask"
    return "repair_current_atom"


def _prompt_rules(
    *,
    next_action: str,
    diagnosis: dict[str, str],
    gate: dict[str, Any],
    atoms: list[dict[str, Any]],
    current_index: int,
) -> list[str]:
    current = atoms[current_index] if atoms and current_index < len(atoms) else {}
    base = [
        "Do not loop on an already banked answer.",
        "Never show diagnosis labels or backend state names to the learner.",
        "Keep the reply to one micro move and exactly one question unless the gate says to close or advance.",
        "Do not ask more than one repair probe for the same missing link.",
    ]
    if next_action == "set_scope_and_advance":
        return [
            "The learner is challenging the scope or premise. Set the scope in one natural sentence, acknowledge the valid boundary concern, and move to the next atom.",
            "Do not ask another vague why/how question for the same point.",
            f"Next atom to teach: {current.get('label', '')}.",
            *base,
        ]
    if next_action == "set_scope_and_close":
        return [
            "The learner has enough mastery and raised a valid scope boundary. Set the scope, summarize the bite, and close it without another probe.",
            *base,
        ]
    if next_action == "advance_to_next_atom":
        return [
            "The previous bite is passed. Acknowledge it in one short sentence and move to the next knowledge atom.",
            "Do not ask again for the same one-sentence distinction, why/how link, or boundary sentence.",
            f"Next atom to teach: {current.get('label', '')}.",
            *base,
        ]
    if next_action == "lesson_bite_complete":
        return [
            "The current bite is passed. Close it naturally and offer the next bite instead of repeating the same check.",
            *base,
        ]
    if next_action == "ask_exit_check":
        return [
            "The learner has a solid paraphrase. Ask one short exit check only; if it is answered, advance next turn.",
            f"Exit-check target: {current.get('review_question') or current.get('label') or ''}.",
            *base,
        ]
    if next_action == "shrink_and_reask":
        return ["The learner needs a smaller step. Give one tiny foothold and ask for one sentence.", *base]
    missing = ", ".join(str(item) for item in gate.get("missing_signals") or []) or diagnosis.get("label", "")
    return [f"Repair only the current atom; missing signal: {missing}. Do not introduce the next atom yet.", *base]


def _student_next_step(next_action: str) -> str:
    return {
        "advance_to_next_atom": "进入下一口",
        "lesson_bite_complete": "本口已收住",
        "ask_exit_check": "收口确认",
        "shrink_and_reask": "缩小一步",
        "repair_current_atom": "修补当前口",
        "set_scope_and_advance": "设定边界并进入下一口",
        "set_scope_and_close": "设定边界并收口",
    }.get(next_action, "正在带学")


def _student_atoms(statuses: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "label": str(atom.get("label") or ""),
            "status": str(atom.get("status") or ""),
            "focus": str(atom.get("focus") or ""),
            "atom_type": str(atom.get("atom_type") or ""),
            "review_question": str(atom.get("review_question") or ""),
            "state_hint": str(atom.get("teaching_status") or ""),
        }
        for atom in statuses
    ]


def _student_learning_signals(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "retrieval": bool(gate.get("retrieval_signal")),
        "evidence": bool(gate.get("grounded_evidence_signal")),
        "causal": bool(gate.get("causal_chain_signal")),
        "boundary": bool(gate.get("boundary_signal")),
        "transfer": bool(gate.get("transfer_signal")),
        "next_action": _student_next_step(str(gate.get("safe_next_action") or "")),
        "probe_count": int(gate.get("same_atom_probe_count") or 0),
        "overquestioning_risk": bool(gate.get("overquestioning_risk")),
    }


def _same_atom_probe_count(assistant_turns: list[str]) -> int:
    count = 0
    for turn in assistant_turns[-6:]:
        normalized = _normalize_text(turn)
        if "？" in turn or "?" in turn or _contains_any(normalized, _PROBE_TERMS):
            if _contains_any(normalized, _PROBE_TERMS):
                count += 1
    return count


def _atom_hit_count(text: str, atoms: list[dict[str, Any]]) -> int:
    hits = 0
    normalized = _normalize_text(text)
    for atom in atoms[:4]:
        key_text = _normalize_text(
            " ".join(
                str(atom.get(key) or "")
                for key in ("label", "focus", "atom_type", "review_question")
            )
        )
        for term in _atom_terms(key_text):
            if term and term in normalized:
                hits += 1
                break
    return hits


def _atom_terms(text: str) -> list[str]:
    terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text))
    for term in _EVIDENCE_TERMS + _CAUSAL_TERMS + _BOUNDARY_TERMS + _TRANSFER_TERMS:
        normalized = _normalize_text(term)
        if normalized and normalized in text:
            terms.add(normalized)
    return sorted(terms)


def _is_rag_agent_boundary_answer(text: str, atoms: list[dict[str, Any]]) -> bool:
    if not _is_rag_agent_atom(atoms):
        return False
    return all(term in text for term in _RAG_AGENT_TERMS) and _contains_any(text, _BOUNDARY_TERMS)


def _is_rag_agent_atom(atoms: list[dict[str, Any]]) -> bool:
    joined = _normalize_text(" ".join(str(atom.get("label") or "") + " " + str(atom.get("focus") or "") for atom in atoms[:2]))
    return all(term in joined for term in _RAG_AGENT_TERMS)


def _asks_for_boundary(text: str) -> bool:
    return _contains_any(text, ("区别", "边界", "范围", "条件", "适合", "不适合"))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(term) in normalized for term in terms if _normalize_text(term))


def _coerce_index(value: Any, count: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    if count <= 0:
        return 0
    return max(0, min(parsed, count - 1))


def _first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _compact(value: Any, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:，。；：)") + "..."
