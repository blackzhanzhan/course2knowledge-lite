from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


LOCAL_PROFILE_VERSION = 1
LOCAL_PEDAGOGY_PROFILES = (
    "neutral",
    "procedural",
    "conceptual",
    "tasked_longform",
)
NEUTRAL_CORE_SLOTS = (
    "concept",
    "rule",
    "procedure_or_ordering_signal",
    "pitfall",
    "example",
    "checkpoint",
)
EXAM_BIAS_TERMS = ("行测", "申论", "公基", "数量关系", "言语理解", "判断推理", "资料分析")


@dataclass(frozen=True)
class MarkdownPedagogyProfile:
    profile_name: str
    description: str
    core_slots: tuple[str, ...]
    exam_terms_forbidden: bool
    exam_semantic_bias_forbidden: bool
    local_profile_only: bool = True


@dataclass(frozen=True)
class MarkdownPedagogySelection:
    primary_profile: str
    detected_tendencies: tuple[str, ...]
    composite_tendency_detectable: bool
    single_primary_shell_enforced: bool
    selection_reason: str
    tasked_longform_priority_on_material_tasks: bool


def build_local_markdown_profiles() -> tuple[MarkdownPedagogyProfile, ...]:
    return (
        MarkdownPedagogyProfile(
            profile_name="neutral",
            description="A domain-agnostic teaching skeleton for non-exam-specific or unknown courses.",
            core_slots=NEUTRAL_CORE_SLOTS,
            exam_terms_forbidden=True,
            exam_semantic_bias_forbidden=True,
        ),
        MarkdownPedagogyProfile(
            profile_name="procedural",
            description="A process-heavy shell that prioritizes formulas, steps, fast-solve paths, and anti-mistake guidance.",
            core_slots=(
                "concept",
                "rule",
                "procedure_or_ordering_signal",
                "pitfall",
                "example",
                "checkpoint",
                "formula",
                "fast_solve",
            ),
            exam_terms_forbidden=False,
            exam_semantic_bias_forbidden=False,
        ),
        MarkdownPedagogyProfile(
            profile_name="conceptual",
            description="A concept-heavy shell that prioritizes disambiguation, trap rules, and teaching-usable judgment language.",
            core_slots=(
                "concept",
                "rule",
                "pitfall",
                "example",
                "checkpoint",
                "disambiguation",
                "trap_rule",
                "minimal_check",
            ),
            exam_terms_forbidden=False,
            exam_semantic_bias_forbidden=False,
        ),
        MarkdownPedagogyProfile(
            profile_name="tasked_longform",
            description="A tasked longform shell for material-evidence extraction, answer skeletoning, targeted patching, and fragment retest.",
            core_slots=(
                "task_lock",
                "evidence_extract",
                "skeleton",
                "targeted_patch",
                "fragment_retest",
                "checkpoint",
            ),
            exam_terms_forbidden=True,
            exam_semantic_bias_forbidden=True,
        ),
    )


def serialize_local_markdown_profiles() -> dict[str, Any]:
    profiles = build_local_markdown_profiles()
    return {
        "local_profile_version": LOCAL_PROFILE_VERSION,
        "local_profiles_do_not_define_global_taxonomy": True,
        "profiles": [asdict(profile) for profile in profiles],
    }


def detect_profile_tendencies(
    *,
    course_name: str,
    lecture_title: str,
    requires_material_evidence: bool = False,
    requires_answer_skeleton: bool = False,
) -> tuple[str, ...]:
    text = " ".join(
        [
            str(course_name or "").strip(),
            str(lecture_title or "").strip(),
        ]
    )
    tendencies: list[str] = []
    if any(keyword in text for keyword in ("数量", "VST", "公式", "行程", "工程", "题", "解题")):
        tendencies.append("procedural")
    if any(keyword in text for keyword in ("公基", "常识", "理论", "思想", "体系", "关系", "辨析", "概念")):
        tendencies.append("conceptual")
    if requires_material_evidence or requires_answer_skeleton:
        tendencies.append("tasked_longform")
    if not tendencies:
        tendencies.append("neutral")
    deduped: list[str] = []
    for item in tendencies:
        if item not in deduped:
            deduped.append(item)
    return tuple(deduped)


def select_primary_markdown_profile(
    *,
    course_name: str,
    lecture_title: str,
    requires_material_evidence: bool = False,
    requires_answer_skeleton: bool = False,
) -> MarkdownPedagogySelection:
    detected_tendencies = detect_profile_tendencies(
        course_name=course_name,
        lecture_title=lecture_title,
        requires_material_evidence=requires_material_evidence,
        requires_answer_skeleton=requires_answer_skeleton,
    )
    if requires_material_evidence and requires_answer_skeleton:
        primary_profile = "tasked_longform"
        selection_reason = (
            "The task explicitly requires material-evidence extraction and answer skeleton construction, "
            "so the longform shell takes precedence over shortform shells."
        )
    elif "procedural" in detected_tendencies:
        primary_profile = "procedural"
        selection_reason = "The lecture text exposes process-bearing, formula-heavy, or fast-solve content."
    elif "conceptual" in detected_tendencies:
        primary_profile = "conceptual"
        selection_reason = "The lecture text exposes concept-dense, disambiguation-heavy, or judgment-rule-heavy content."
    else:
        primary_profile = "neutral"
        selection_reason = "No stronger typed tendency is exposed, so the neutral teaching skeleton remains the safest default."

    return MarkdownPedagogySelection(
        primary_profile=primary_profile,
        detected_tendencies=detected_tendencies,
        composite_tendency_detectable=len(detected_tendencies) > 1,
        single_primary_shell_enforced=True,
        selection_reason=selection_reason,
        tasked_longform_priority_on_material_tasks=bool(
            requires_material_evidence and requires_answer_skeleton
        ),
    )


def neutral_semantic_exam_bias_detected(*, text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    exam_term_hit = any(term in normalized for term in EXAM_BIAS_TERMS)
    exam_first_framing_hit = any(
        fragment in normalized for fragment in ("高频", "快速拿分", "判断技巧", "常考方向", "速记")
    )
    return bool(exam_term_hit or exam_first_framing_hit)


__all__ = [
    "LOCAL_PEDAGOGY_PROFILES",
    "LOCAL_PROFILE_VERSION",
    "NEUTRAL_CORE_SLOTS",
    "MarkdownPedagogyProfile",
    "MarkdownPedagogySelection",
    "build_local_markdown_profiles",
    "serialize_local_markdown_profiles",
    "detect_profile_tendencies",
    "select_primary_markdown_profile",
    "neutral_semantic_exam_bias_detected",
]
