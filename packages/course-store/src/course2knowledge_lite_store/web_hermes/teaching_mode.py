from __future__ import annotations

import re
from typing import Any


WEB_TEACHING_MODE_CONTRACT = "web_mother_style_teaching_packet_contract"


def build_web_teaching_mode_packet(
    *,
    user_intent: str,
    course_binding: dict[str, Any] | None = None,
    course_context: dict[str, Any] | None = None,
    teaching_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project child-local course evidence into the mother teaching packet shape."""

    binding = dict(course_binding or {})
    context = dict(course_context or {})
    course = dict(context.get("course") or {})
    lecture = dict(context.get("lecture") or {})
    cards = _normalize_cards(context.get("knowledge_cards") or [])
    evidence = _selected_evidence(context=context, cards=cards)
    atoms = _knowledge_atoms(cards=cards, lecture=lecture, evidence=evidence)
    control = dict(teaching_control or {})
    control_visible = dict(control.get("student_visible") or {})
    if control_visible.get("knowledge_atoms"):
        atoms = list(control_visible.get("knowledge_atoms") or [])
    focus = _focus_text(atoms=atoms, evidence=evidence, lecture=lecture, course=course)
    course_title = _compact(course.get("title") or binding.get("child_course_title") or "", default="current course", limit=96)
    lecture_title = _compact(lecture.get("title") or "", default="", limit=96)
    binding_status = str(binding.get("binding_status") or "unbound").strip() or "unbound"

    return {
        "contract": WEB_TEACHING_MODE_CONTRACT,
        "mode_source": "copied_from_mother_learning_companion_shape",
        "status": "ready" if focus else "blocked_no_local_evidence",
        "source_boundary": {
            "course_surface": "child_local_course_store",
            "binding_status": binding_status,
            "formal_queue_writeback": False,
            "uses_personal_global_queue": False,
            "student_rule": "Do not discuss binding status or backend routing. Teach from the provided course evidence.",
        },
        "course_context": {
            "course_title": course_title,
            "lesson_title": lecture_title,
            "evidence_status": "local_evidence_available" if evidence else "title_only",
        },
        "chat_lesson_capsule": {
            "status": "ready" if evidence or focus else "blocked",
            "teaching_contract_mode": "chat_lesson_capsule_lite",
            "course_context": {
                "course_title": course_title,
                "module_title": lecture_title or course_title,
            },
            "selected_evidence": evidence,
            "current_hidden_focus": focus,
        },
        "student_facing_packet": _student_facing_packet(focus=focus, course_title=course_title),
        "companion_control_loop": _companion_control_loop(focus=focus),
        "answer_diagnosis_loop": _answer_diagnosis_loop(focus=focus),
        "completion_contract": _completion_contract(),
        "frontdesk_next_actions": [
            "Use the teaching packet as the source of truth for this Web turn.",
            "Start with exactly one small teaching move and one question.",
            "Do not answer broadly like search. Do not dump a full lesson.",
            "Use selected evidence only as grounding; never expose internal identifiers.",
            "After the learner answers, diagnose silently, name one concrete micro-win, then repair, probe, or ask one exit-check question.",
        ],
        "student_visible_state": {
            "progress_ratio_label": control.get("progress_ratio_label") or _progress_ratio_label(atoms),
            "next_step_label": control_visible.get("next_step_label") or "正在带学",
            "knowledge_atoms": atoms,
        },
        "teaching_control": control,
        "latest_user_intent_summary": _compact(user_intent, default="", limit=180),
    }


def teaching_packet_prompt_context(packet: dict[str, Any]) -> str:
    """Return a compact text version of the packet for the live gateway prompt."""

    capsule = dict(packet.get("chat_lesson_capsule") or {})
    student = dict(packet.get("student_facing_packet") or {})
    state = dict(packet.get("student_visible_state") or {})
    evidence_lines = []
    for item in capsule.get("selected_evidence") or []:
        if not isinstance(item, dict):
            continue
        title = _compact(item.get("section_title"), default="lesson evidence", limit=48)
        excerpt = _compact(item.get("excerpt_text"), default="", limit=180)
        if excerpt:
            evidence_lines.append(f"- {title}: {excerpt}")
    atom_lines = []
    for atom in state.get("knowledge_atoms") or []:
        if not isinstance(atom, dict):
            continue
        label = _compact(atom.get("label"), default="", limit=60)
        focus = _compact(atom.get("focus"), default="", limit=90)
        question = _compact(atom.get("review_question"), default="", limit=90)
        atom_type = _compact(atom.get("atom_type"), default="", limit=24)
        if label:
            suffix = f" | check: {question}" if question else ""
            atom_lines.append(f"- {label} ({atom_type or 'atom'}): {focus}{suffix}")
    return "\n".join(
        [
            "Mother-style teaching packet:",
            f"Contract: {packet.get('contract', '')}",
            f"Course: {dict(packet.get('course_context') or {}).get('course_title', '')}",
            f"Lesson: {dict(packet.get('course_context') or {}).get('lesson_title', '')}",
            f"Hidden focus: {capsule.get('current_hidden_focus', '')}",
            f"First-turn template: {student.get('sendable_first_turn_template', '')}",
            f"First-turn contract: {student.get('first_turn_contract', '')}",
            "Knowledge atom order:",
            "\n".join(atom_lines[:6]) or "- current lesson entry",
            "Grounding evidence:",
            "\n".join(evidence_lines[:4]) or "- No transcript excerpt is available; use only the course or lesson title as a starting point and be honest.",
            "Control loop:",
            "One micro explanation, one question, wait for the learner. If the learner is vague, shrink the step. If the learner sounds fluent but skips why/how, ask for the missing link. If the learner has the boundary wrong, ask for one contrast sentence.",
        ]
    )


def _student_facing_packet(*, focus: str, course_title: str) -> dict[str, Any]:
    safe_focus = _compact(focus, default=course_title or "当前小点", limit=96)
    return {
        "opening_line": "我来带节奏。我们一次只抓一个小点，答完我再带你往下走。",
        "sendable_first_turn_template": (
            f"我先把这一口缩小到一个点：{safe_focus}。"
            "你先用一句话说说，这里最该抓住的判断是什么？"
        ),
        "first_turn_contract": {
            "max_chars": 280,
            "must_end_with_one_question": True,
            "one_small_idea_only": True,
            "no_full_lesson_dump": True,
            "no_numbered_backend_report": True,
            "send_exact_template_or_shorter": True,
            "no_bullets_examples_or_contrasts_before_answer": True,
        },
        "first_turn_forbidden_additions": [
            "bullet list",
            "worked example",
            "full lesson exposition",
            "second question before the learner answers",
        ],
        "next_prompt_hint": "先让学生用自己的话复述一个判断，再决定补台阶、追问因果，或进入下一个小点。",
        "burden_shift": "学生只需要聊天作答；系统负责收缩范围、排序知识原子和推进节奏。",
        "momentum_rule": "一轮只推进一个小胜利。",
        "forbidden_student_visible_fields": [
            "queue_id",
            "node_id",
            "course_node_key",
            "mastery_level",
            "review_stage",
            "slot_id",
        ],
        "next_step_label": "正在带学",
    }


def _companion_control_loop(*, focus: str) -> dict[str, Any]:
    return {
        "current_hidden_focus": _compact(focus, default="当前小点", limit=120),
        "turn_rule": "one_micro_step_only",
        "after_student_answer": [
            "silently classify the answer",
            "name one concrete micro-win in natural language",
            "repair, probe, exit-check, or move to the next atom",
        ],
        "completion_allowed": False,
        "completion_rule": "Web display does not complete formal queue items.",
    }


def _answer_diagnosis_loop(*, focus: str) -> dict[str, Any]:
    return {
        "current_hidden_focus": _compact(focus, default="当前小点", limit=120),
        "labels": [
            {
                "label": "low_foundation_blank",
                "detect": "blank, confused, or cannot paraphrase",
                "next_move": "give one tiny foothold and ask for a one-sentence paraphrase",
            },
            {
                "label": "surface_terms_only",
                "detect": "repeats nouns but does not connect them",
                "next_move": "ask how the two named terms relate in this lesson slice",
            },
            {
                "label": "fluent_missing_causal_chain",
                "detect": "sounds confident but skips why or how",
                "next_move": "ask one why/how question tied to the selected evidence",
            },
            {
                "label": "boundary_confusion",
                "detect": "uses the idea in the wrong scope",
                "next_move": "ask for one contrast or boundary sentence",
            },
            {
                "label": "solid_paraphrase",
                "detect": "can paraphrase and give a reason",
                "next_move": "run one short exit check or small variation",
            },
        ],
        "student_visible_rule": "Never show labels or rubric headings to the learner.",
    }


def _completion_contract() -> dict[str, Any]:
    return {
        "completion_tool": "",
        "formal_writeback_allowed": False,
        "required_before_real_completion": [
            "grounded explanation",
            "learner response",
            "response diagnosis",
            "multi-turn dialogue",
            "exit check or correction",
        ],
    }


def _selected_evidence(*, context: dict[str, Any], cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for card in cards[:4]:
        title = _compact(card.get("title"), default="knowledge atom", limit=72)
        body = _compact(card.get("body"), default="", limit=220)
        if body:
            evidence.append({"section_title": title, "excerpt_text": body})
    if evidence:
        return evidence

    reader = dict(context.get("reader") or {})
    for segment in (reader.get("segments") or [])[:4]:
        if not isinstance(segment, dict):
            continue
        text = _compact(segment.get("text"), default="", limit=220)
        if text:
            evidence.append({"section_title": "transcript excerpt", "excerpt_text": text})
    return evidence


def _knowledge_atoms(
    *,
    cards: list[dict[str, Any]],
    lecture: dict[str, Any],
    evidence: list[dict[str, str]],
) -> list[dict[str, str]]:
    atoms: list[dict[str, str]] = []
    for index, card in enumerate(cards[:8]):
        review_questions = card.get("review_questions") if isinstance(card.get("review_questions"), list) else []
        review_question = ""
        for item in review_questions:
            review_question = _compact(item, default="", limit=96)
            if review_question:
                break
        atoms.append(
            {
                "label": _compact(card.get("title"), default=f"知识原子 {index + 1}", limit=72),
                "status": "当前口" if index == 0 else "候选",
                "progress": f"{index + 1}/{max(len(cards), 1)}",
                "focus": _compact(card.get("summary") or card.get("body"), default="等待对话中点亮", limit=96),
                "atom_type": _compact(card.get("atom_type"), default="concept", limit=24),
                "review_question": review_question,
                "confidence": _compact(card.get("confidence"), default="", limit=16),
                "state_hint": "teaching_focus" if index == 0 else "waiting",
            }
        )
    if atoms:
        return atoms
    for index, item in enumerate(evidence[:4]):
        atoms.append(
            {
                "label": _compact(item.get("section_title"), default=f"课时片段 {index + 1}", limit=72),
                "status": "当前口" if index == 0 else "候选",
                "progress": f"{index + 1}/{max(len(evidence), 1)}",
                "focus": _compact(item.get("excerpt_text"), default="等待对话中点亮", limit=96),
                "state_hint": "teaching_focus" if index == 0 else "waiting",
            }
        )
    if atoms:
        return atoms
    title = _compact(lecture.get("title"), default="当前课时入口", limit=72)
    return [
        {
            "label": title,
            "status": "当前口",
            "progress": "1/1",
            "focus": "当前课时还没有可用转写，先从标题建立一个可回答的问题。",
            "state_hint": "title_only",
        }
    ]


def _focus_text(
    *,
    atoms: list[dict[str, str]],
    evidence: list[dict[str, str]],
    lecture: dict[str, Any],
    course: dict[str, Any],
) -> str:
    for atom in atoms:
        text = _compact(atom.get("focus"), default="", limit=96)
        if text:
            return text
    for item in evidence:
        text = _compact(item.get("excerpt_text"), default="", limit=96)
        if text:
            return text
    return _compact(lecture.get("title") or course.get("title"), default="当前小点", limit=96)


def _progress_ratio_label(atoms: list[dict[str, str]]) -> str:
    if not atoms:
        return ""
    return f"1/{len(atoms)}"


def _normalize_cards(raw_cards: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []
    cards = [dict(card) for card in raw_cards if isinstance(card, dict)]
    cards.sort(key=lambda card: (str(card.get("lecture_id") or ""), str(card.get("card_id") or "")))
    return cards


def _compact(value: Any, *, default: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()
    if not text:
        return default
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:，。；：、") + "..."
