from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .adapters import RequestRetryTelemetryRecorder

from .course_profiles import select_primary_markdown_profile
from .compile_gateway import request_compile_json
from .deepseek import (
    DEEPSEEK_MODEL,
    DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
)

REDUCE_MODEL_CRITICAL_FIELDS = (
    "lecture_title",
    "lecture_summary",
    "sections",
    "review_questions",
    "prerequisites",
    "pitfalls",
    "minimal_examples",
)
REDUCE_PYTHON_DERIVED_FIELDS = (
    "followup_scaffold",
    "feedback_routes",
    "search_hooks",
)


@dataclass(frozen=True)
class ReducePromptBudget:
    anchor_quote_chars: int
    atom_summary_chars: int
    atom_body_chars: int
    relation_quote_chars: int
    max_atoms_per_chunk: int | None = None
    max_relations_per_chunk: int | None = None


DEFAULT_REDUCE_PROMPT_BUDGET = ReducePromptBudget(
    anchor_quote_chars=40,
    atom_summary_chars=60,
    atom_body_chars=100,
    relation_quote_chars=30,
    max_atoms_per_chunk=None,
    max_relations_per_chunk=None,
)

FAST_REDUCE_PROMPT_BUDGET = ReducePromptBudget(
    anchor_quote_chars=24,
    atom_summary_chars=32,
    atom_body_chars=56,
    relation_quote_chars=14,
    max_atoms_per_chunk=3,
    max_relations_per_chunk=1,
)

FAST_REDUCE_GUARD_TOKEN_LIMIT = 3000
FAST_REDUCE_MAX_TOKENS = 4096


def estimate_reduce_prompt_tokens(prompt: str) -> int:
    # Lightweight heuristic for white-box probe use only.
    return max(1, int(round(len(str(prompt or "")) / 4.0)))


def _truncate_text(raw_value: Any, *, limit: int) -> str:
    normalized = str(raw_value or "").strip()
    if limit <= 0:
        return ""
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "…"


def _score_atom(atom: dict[str, Any]) -> tuple[int, int, int, str]:
    anchor_count = len(atom.get("anchor_ids") or [])
    atom_type = str(atom.get("atom_type", "")).strip()
    title = str(atom.get("canonical_title", "")).strip()
    priority = 0
    if atom_type in {"误区", "pitfall"}:
        priority = 4
    elif atom_type in {"方法", "strategy"}:
        priority = 3
    elif atom_type in {"概念", "concept"}:
        priority = 2
    return (-priority, -anchor_count, -len(title), title)


def _score_relation(relation: dict[str, Any]) -> tuple[int, int, str]:
    anchor_count = len(relation.get("anchor_ids") or [])
    relation_type = str(relation.get("relation_type", "")).strip()
    return (-anchor_count, -len(relation_type), relation_type)


def _compact_mapped_chunks(
    mapped_chunks: list[dict[str, Any]],
    *,
    budget: ReducePromptBudget = DEFAULT_REDUCE_PROMPT_BUDGET,
) -> list[dict[str, Any]]:
    compact_chunks: list[dict[str, Any]] = []
    for chunk in mapped_chunks:
        if not isinstance(chunk, dict):
            continue
        anchors = []
        for anchor in chunk.get("anchors") or []:
            if not isinstance(anchor, dict):
                continue
            anchors.append(
                {
                    "anchor_id": str(anchor.get("anchor_id", "")).strip(),
                    "start_timestamp": str(anchor.get("start_timestamp", "")).strip(),
                    "end_timestamp": str(anchor.get("end_timestamp", "")).strip(),
                    "evidence_quote": _truncate_text(
                        anchor.get("evidence_quote", ""),
                        limit=budget.anchor_quote_chars,
                    ),
                }
            )
        atoms = []
        raw_atoms = [
            atom for atom in (chunk.get("atoms") or []) if isinstance(atom, dict)
        ]
        raw_atoms.sort(key=_score_atom)
        if budget.max_atoms_per_chunk is not None:
            raw_atoms = raw_atoms[: budget.max_atoms_per_chunk]
        for atom in raw_atoms:
            if not isinstance(atom, dict):
                continue
            atoms.append(
                {
                    "atom_id": str(atom.get("atom_id", "")).strip(),
                    "canonical_title": str(
                        atom.get("canonical_title", "")
                    ).strip(),
                    "atom_type": str(atom.get("atom_type", "")).strip(),
                    "summary": _truncate_text(
                        atom.get("summary", ""),
                        limit=budget.atom_summary_chars,
                    ),
                    "body_markdown": _truncate_text(
                        atom.get("body_markdown", ""),
                        limit=budget.atom_body_chars,
                    ),
                    "anchor_ids": list(atom.get("anchor_ids") or []),
                }
            )
        relations = []
        raw_relations = [
            relation
            for relation in (chunk.get("relations") or [])
            if isinstance(relation, dict)
        ]
        raw_relations.sort(key=_score_relation)
        if budget.max_relations_per_chunk is not None:
            raw_relations = raw_relations[: budget.max_relations_per_chunk]
        for relation in raw_relations:
            if not isinstance(relation, dict):
                continue
            relations.append(
                {
                    "source_atom_id": str(
                        relation.get("source_atom_id", "")
                    ).strip(),
                    "target_atom_id": str(
                        relation.get("target_atom_id", "")
                    ).strip(),
                    "relation_type": str(
                        relation.get("relation_type", "")
                    ).strip(),
                    "evidence_quote": _truncate_text(
                        relation.get("evidence_quote", ""),
                        limit=budget.relation_quote_chars,
                    ),
                    "anchor_ids": list(relation.get("anchor_ids") or []),
                }
            )
        compact_chunks.append(
            {
                "chunk_id": str(chunk.get("chunk_id", "")).strip(),
                "chunk_summary": _truncate_text(
                    chunk.get("chunk_summary", ""), limit=80
                ),
                "anchors": anchors,
                "atoms": atoms,
                "relations": relations,
            }
        )
    return compact_chunks


def build_text_reduce_prompt(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    mapped_chunks: list[dict[str, Any]] | None = None,
    compact_mapped_chunks: list[dict[str, Any]] | None = None,
    lite_map_mode: bool = False,
) -> str:
    profile = select_primary_markdown_profile(
        course_name=course_name,
        lecture_title=lecture_title,
    )
    if profile.primary_profile == "procedural":
        profile_guidance = (
            " 当前 shortform reduce path = procedural。"
            " 强化公式、步骤、快解策略、易错点与最小例题的教学可用性。"
            " 要求答案压缩但锋利，不能把动作性内容抹平成概念总结。"
        )
    elif profile.primary_profile == "conceptual":
        profile_guidance = (
            " 当前 shortform reduce path = conceptual。"
            " 强化易混辨析、高频错判、条件-结论式判断规则、最小抽问。"
            " 不要把概念课假装 procedural 化，也不要只写空泛框架总结。"
        )
    else:
        profile_guidance = (
            " 当前 shortform reduce path = neutral。"
            " 保持领域中性的教学骨架，不得带考试优先或得分导向的 framing。"
        )
    resolved_compact_chunks = compact_mapped_chunks
    if resolved_compact_chunks is None:
        if mapped_chunks is None:
            raise ValueError("mapped_chunks or compact_mapped_chunks is required")
        resolved_compact_chunks = _compact_mapped_chunks(mapped_chunks)
    compact_mapped_chunks_json = json.dumps(
        resolved_compact_chunks, ensure_ascii=False, separators=(",", ":")
    )
    model_fields_text = "、".join(REDUCE_MODEL_CRITICAL_FIELDS)
    derived_fields_text = "、".join(REDUCE_PYTHON_DERIVED_FIELDS)
    if lite_map_mode:
        intro = (
            "你是通用课程讲义总管。"
            " 你将收到这节课的原始字幕文本（按时间分段）。"
            " 请直接从字幕中提取结构化讲义。"
        )
    else:
        intro = (
            "你是通用课程讲义总管。"
            " 你将收到同一讲的多个 chunk 斥候情报。"
        )
    return (
        f"{intro}"
        f"{profile_guidance}"
        f" 请合成为 {model_fields_text}。"
        " sections 每项必须包含 heading、body、anchor_ids。"
        " prerequisites 每项必须包含 title、why_it_matters、anchor_ids；优先给出 3-5 条，不要把多个前置压成一句空话。why_it_matters 尽量控制在 80 字以内。"
        " pitfalls 每项必须包含 title、why_wrong、correction、anchor_ids；优先给出 2-5 条。why_wrong 与 correction 尽量控制在 80 字以内。"
        " minimal_examples 每项必须包含 title、problem、steps、takeaway、anchor_ids；至少给出 1 条。"
        f" {derived_fields_text} 由 Python 后处理阶段补齐，本轮不要输出这三项。"
        " 这些字段用于 AI 运行时动态追问和答错分流，不是静态问题清单。"
        " 不要把不同追问目标合并成一条笼统 scaffold，也不要把多个检索意图压缩成一个宽泛搜索词。"
        + (" 只保留对陪学真正有用的结构化结果，不要逐字复述字幕。" if lite_map_mode else " 你收到的是精简版 chunk 情报，不要复述所有内容，只保留对陪学真正有用的结构化结果。")
        + " 只输出 JSON。"
        f"\n课程名: {course_name}"
        f"\n讲次名: {lecture_title}"
        f"\n来源: {source_url}"
        + (f"\n原始字幕分段(JSON):\n{compact_mapped_chunks_json}" if lite_map_mode else f"\nChunk 斥候情报(JSON):\n{compact_mapped_chunks_json}")
    )


def build_reduce_compact_payload(
    mapped_chunks: list[dict[str, Any]],
    *,
    budget: ReducePromptBudget = DEFAULT_REDUCE_PROMPT_BUDGET,
) -> list[dict[str, Any]]:
    return _compact_mapped_chunks(mapped_chunks, budget=budget)


def _count_compact_payload_items(
    compact_chunks: list[dict[str, Any]],
) -> tuple[int, int, int]:
    anchor_count = 0
    atom_count = 0
    relation_count = 0
    for chunk in compact_chunks:
        anchor_count += len(chunk.get("anchors") or [])
        atom_count += len(chunk.get("atoms") or [])
        relation_count += len(chunk.get("relations") or [])
    return anchor_count, atom_count, relation_count


def build_input_guarded_reduce_payload(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    mapped_chunks: list[dict[str, Any]],
    fast_reduce_mode: bool = False,
    input_guard_token_limit: int = FAST_REDUCE_GUARD_TOKEN_LIMIT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    default_compact = build_reduce_compact_payload(
        mapped_chunks,
        budget=DEFAULT_REDUCE_PROMPT_BUDGET,
    )
    prompt_before = build_text_reduce_prompt(
        course_name=course_name,
        lecture_title=lecture_title,
        source_url=source_url,
        compact_mapped_chunks=default_compact,
    )
    estimated_prompt_tokens_before = estimate_reduce_prompt_tokens(prompt_before)
    if not fast_reduce_mode:
        before_anchor_count, before_atom_count, before_relation_count = _count_compact_payload_items(
            default_compact
        )
        return default_compact, {
            "fast_reduce_mode_enabled": False,
            "input_guard_triggered": False,
            "estimated_prompt_tokens_before": estimated_prompt_tokens_before,
            "estimated_prompt_tokens_after": estimated_prompt_tokens_before,
            "pruned_anchor_count": 0,
            "pruned_atom_count": 0,
            "pruned_relation_count": 0,
            "compact_anchor_count": before_anchor_count,
            "compact_atom_count": before_atom_count,
            "compact_relation_count": before_relation_count,
            "reduce_max_tokens_before": DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
            "reduce_max_tokens_after": DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
        }

    guarded_compact = build_reduce_compact_payload(
        mapped_chunks,
        budget=FAST_REDUCE_PROMPT_BUDGET,
    )
    prompt_after = build_text_reduce_prompt(
        course_name=course_name,
        lecture_title=lecture_title,
        source_url=source_url,
        compact_mapped_chunks=guarded_compact,
    )
    estimated_prompt_tokens_after = estimate_reduce_prompt_tokens(prompt_after)
    before_anchor_count, before_atom_count, before_relation_count = _count_compact_payload_items(
        default_compact
    )
    after_anchor_count, after_atom_count, after_relation_count = _count_compact_payload_items(
        guarded_compact
    )
    input_guard_triggered = estimated_prompt_tokens_before > input_guard_token_limit
    return guarded_compact, {
        "fast_reduce_mode_enabled": True,
        "input_guard_triggered": input_guard_triggered,
        "estimated_prompt_tokens_before": estimated_prompt_tokens_before,
        "estimated_prompt_tokens_after": estimated_prompt_tokens_after,
        "pruned_anchor_count": max(0, before_anchor_count - after_anchor_count),
        "pruned_atom_count": max(0, before_atom_count - after_atom_count),
        "pruned_relation_count": max(0, before_relation_count - after_relation_count),
        "compact_anchor_count": after_anchor_count,
        "compact_atom_count": after_atom_count,
        "compact_relation_count": after_relation_count,
        "reduce_max_tokens_before": DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
        "reduce_max_tokens_after": FAST_REDUCE_MAX_TOKENS,
    }


def build_reduce_field_ownership_map() -> dict[str, list[str]]:
    return {
        "model_owned_fields": list(REDUCE_MODEL_CRITICAL_FIELDS),
        "python_deterministic_fields": list(REDUCE_PYTHON_DERIVED_FIELDS),
    }


def reduce_mapped_chunks(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    mapped_chunks: list[dict[str, Any]],
    compact_mapped_chunks: list[dict[str, Any]] | None = None,
    api_key: str | None = None,
    model: str = DEEPSEEK_MODEL,
    max_tokens: int = DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
    max_concurrent_requests: int = 2,
    telemetry_recorder: RequestRetryTelemetryRecorder | None = None,
    request_label: str = "",
    compile_provider: str | None = None,
    source_kind: str = "",
    multimodal_mode: str = "unknown",
    lite_map_mode: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return request_compile_json(
        stage_name="reduce",
        system_prompt="你是严格的课程讲义 Reduce JSON 总管。",
        user_prompt=build_text_reduce_prompt(
            course_name=course_name,
            lecture_title=lecture_title,
            source_url=source_url,
            mapped_chunks=mapped_chunks,
            compact_mapped_chunks=compact_mapped_chunks,
            lite_map_mode=lite_map_mode,
        ),
        provider=compile_provider,
        api_key=api_key,
        model=model,
        source_kind=source_kind,
        multimodal_mode=multimodal_mode,
        max_tokens=max_tokens,
        max_concurrent_requests=max_concurrent_requests,
        telemetry_recorder=telemetry_recorder,
        request_label=request_label or "reduce",
        response_schema={"type": "object"},
    )
