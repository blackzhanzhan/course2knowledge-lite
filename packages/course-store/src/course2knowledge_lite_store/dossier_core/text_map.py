from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from typing import Any

from .adapters import RequestRetryTelemetryRecorder, format_timestamp_anchor

from .course_profiles import select_primary_markdown_profile
from .compile_gateway import ENV_PROVIDER_KEY, request_compile_json
from .deepseek import DEEPSEEK_MODEL


@dataclass(frozen=True)
class TextMapBudget:
    chunk_summary_sentences: int
    chunk_summary_chars: int
    anchor_limit: int
    anchor_quote_chars: int
    atom_limit: int
    atom_summary_chars: int
    atom_body_chars: int
    relation_limit: int
    relation_quote_chars: int


DEFAULT_TEXT_MAP_BUDGET = TextMapBudget(
    chunk_summary_sentences=2,
    chunk_summary_chars=100,
    anchor_limit=12,
    anchor_quote_chars=50,
    atom_limit=6,
    atom_summary_chars=50,
    atom_body_chars=160,
    relation_limit=6,
    relation_quote_chars=30,
)

FAST_TEXT_MAP_BUDGET = TextMapBudget(
    chunk_summary_sentences=1,
    chunk_summary_chars=60,
    anchor_limit=6,
    anchor_quote_chars=24,
    atom_limit=4,
    atom_summary_chars=28,
    atom_body_chars=90,
    relation_limit=3,
    relation_quote_chars=18,
)


LOCAL_QWEN_PROVIDER = "llama_cpp_local"


def _local_qwen_provider_requested(compile_provider: str | None) -> bool:
    requested = str(compile_provider or "").strip()
    if requested and requested != "auto":
        return requested == LOCAL_QWEN_PROVIDER
    env_provider = str(os.getenv(ENV_PROVIDER_KEY, "") or "").strip()
    return env_provider == LOCAL_QWEN_PROVIDER


def _format_chunk_lines_for_prompt(chunk: dict[str, Any]) -> str:
    raw_lines = [
        str(line).strip()
        for line in str(chunk.get("text", "") or "").splitlines()
        if str(line).strip()
    ]
    if not raw_lines:
        raw_text = str(chunk.get("text", "") or "").strip()
        if raw_text:
            raw_lines = [raw_text]
    source_line_ids = [
        int(item)
        for item in (chunk.get("source_line_ids") or [])
        if str(item).strip()
    ]
    if not source_line_ids:
        line_start = int(chunk.get("line_start", 1) or 1)
        source_line_ids = list(range(line_start, line_start + max(1, len(raw_lines))))
    if len(raw_lines) < len(source_line_ids):
        raw_lines.extend([""] * (len(source_line_ids) - len(raw_lines)))
    return "\n".join(
        f"{line_id}: {text}"
        for line_id, text in zip(source_line_ids, raw_lines, strict=False)
        if str(text).strip()
    )


def build_local_qwen_text_map_prompt(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    chunk: dict[str, Any],
    budget: TextMapBudget = DEFAULT_TEXT_MAP_BUDGET,
) -> str:
    subtitle_lines = _format_chunk_lines_for_prompt(chunk)
    chunk_id = str(chunk["chunk_id"])
    schema = {
        "chunk_summary": "one sentence grounded in SUBTITLE_TEXT",
        "anchors": [
            {
                "anchor_id": f"{chunk_id}_anc_001",
                "modality": "subtitle",
                "source_line_ids": [1],
                "start_timestamp": str(chunk.get("start_timestamp", "")).strip(),
                "end_timestamp": str(chunk.get("end_timestamp", "")).strip(),
                "suggested_screenshot_timestamp": str(chunk.get("start_timestamp", "")).strip(),
                "evidence_quote": "short exact quote copied from SUBTITLE_TEXT",
                "confidence": 0.8,
            }
        ],
        "atoms": [
            {
                "canonical_title": "concept or method from SUBTITLE_TEXT",
                "atom_type": "concept|method|rule|tactic|pitfall",
                "summary": "short grounded summary",
                "body_markdown": "compact teaching note based only on SUBTITLE_TEXT",
                "anchor_ids": [f"{chunk_id}_anc_001"],
                "source_anchor_id": f"{chunk_id}_anc_001",
                "status": "locked",
                "confidence": 0.8,
            }
        ],
        "relations": [
            {
                "source_atom_id": "atom id or canonical title from atoms",
                "target_atom_id": "atom id or canonical title from atoms",
                "relation_type": "prerequisite|causes|leads_to|contrasts|refines|part_of",
                "anchor_ids": [f"{chunk_id}_anc_001"],
                "evidence_quote": "short exact quote copied from SUBTITLE_TEXT",
                "confidence": 0.8,
            }
        ],
    }
    return (
        "LOCAL_QWEN_MAP_PROFILE_V1\n"
        "Task: extract a small MAP payload from one subtitle chunk.\n"
        "Use ONLY the text inside SUBTITLE_TEXT. Do not explain the schema. Do not invent examples.\n"
        "If a field cannot be grounded in SUBTITLE_TEXT, return an empty array for that field.\n"
        f"Course: {course_name}\n"
        f"Lecture: {lecture_title}\n"
        f"Source: {source_url}\n"
        f"Chunk ID: {chunk_id}\n"
        f"Time: {chunk['start_timestamp']} -> {chunk['end_timestamp']}\n"
        f"Line range: {chunk['line_start']} -> {chunk['line_end']}\n"
        "<SUBTITLE_TEXT>\n"
        f"{subtitle_lines}\n"
        "</SUBTITLE_TEXT>\n"
        "Grounding rules:\n"
        "- evidence_quote must be copied verbatim from SUBTITLE_TEXT and kept short.\n"
        "- source_line_ids must refer to the numbered subtitle lines above.\n"
        f"- Return at most {budget.anchor_limit} anchors, {budget.atom_limit} atoms, and {budget.relation_limit} relations.\n"
        f"- Keep chunk_summary within {budget.chunk_summary_sentences} sentence(s).\n"
        "- anchor_ids and source_anchor_id must be string ids from the anchors array, not numbers.\n"
        "- Do not output markdown fences, comments, or prose before/after JSON.\n"
        "OUTPUT_JSON_SCHEMA:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def build_text_map_prompt(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    chunk: dict[str, Any],
    budget: TextMapBudget = DEFAULT_TEXT_MAP_BUDGET,
) -> str:
    profile = select_primary_markdown_profile(
        course_name=course_name,
        lecture_title=lecture_title,
    )
    if profile.primary_profile == "procedural":
        profile_guidance = (
            " 当前 shortform 教学壳为 procedural。"
            " 优先提取可直接指导解题或执行的公式、步骤、快解策略、易错点与反例。"
            " 不要把关键规则压成抽象概念空话。"
        )
    elif profile.primary_profile == "conceptual":
        profile_guidance = (
            " 当前 shortform 教学壳为 conceptual。"
            " 优先提取可教学的概念边界、易混辨析点、判断规则、高频错判与最小抽问所需信息。"
            " 不要强行 procedural 化，不要假装所有内容都能写成解题步骤。"
        )
    else:
        profile_guidance = (
            " 当前 shortform 教学壳为 neutral。"
            " 输出必须保持领域中性，不得默认采用考试教练口吻或应试优先 framing。"
        )
    return (
        "你是通用课程讲义斥候。"
        " 你只负责处理单个字幕切片，提炼出后续整讲 Reduce 所需的结构化情报。"
        f"{profile_guidance}"
        " 如果字幕开头出现明显的暖场音乐歌词（如不连贯的短句、歌曲歌词、重复的感叹词），直接忽略，从正式课程内容开始提取。"
        " 请提取 chunk_summary、anchors、atoms、relations。"
        " 执行严格但以知识问答可用为目标的输出预算控制：保留后续 Reduce 和问答真正需要的高价值信息，禁止为了省 token 过度合并无关证据。"
        f" chunk_summary 最多 {budget.chunk_summary_sentences} 句，尽量控制在 {budget.chunk_summary_chars} 字以内。"
        f" anchors 最多 {budget.anchor_limit} 条，优先覆盖不同知识点与关键转折，避免用一条巨型 anchor 覆盖整段内容。"
        " 每条 anchor 只允许携带 source_line_ids、start_timestamp、end_timestamp、suggested_screenshot_timestamp、evidence_quote。"
        f" evidence_quote 必须是短引文，尽量控制在 {budget.anchor_quote_chars} 字以内，只摘最关键原话。"
        f" atoms 最多 {budget.atom_limit} 条，只保留高价值概念、战术、规则、方法或常见误区。"
        " 每条 atom 必须携带 canonical_title、atom_type、summary、body_markdown、anchor_ids、source_anchor_id、status、confidence。"
        f" atom 的 summary 尽量控制在 {budget.atom_summary_chars} 字以内；body_markdown 尽量控制在 {budget.atom_body_chars} 字以内，优先保留可直接问答的关键规则、前提、误区或步骤。"
        f" relations 最多 {budget.relation_limit} 条；如果关系不关键或证据不足，宁可返回空数组。"
        " 每条 relation 必须携带 source_atom_id、target_atom_id、relation_type、anchor_ids、evidence_quote、confidence。"
        f" relation 的 evidence_quote 同样必须短小，尽量控制在 {budget.relation_quote_chars} 字以内。"
        " 禁止输出重复 atoms、重复 relations、客套话、解释性前后缀、Markdown 代码块。"
        " 只输出 JSON。"
        f"\n课程名: {course_name}"
        f"\n讲次名: {lecture_title}"
        f"\n来源: {source_url}"
        f"\nChunk ID: {chunk['chunk_id']}"
        f"\n时间范围: {chunk['start_timestamp']} -> {chunk['end_timestamp']}"
        f"\n行号范围: {chunk['line_start']} -> {chunk['line_end']}"
        f"\n字幕正文:\n{chunk['text']}"
    )


def _parse_second_precision_timestamp(raw_value: str) -> float:
    cleaned = str(raw_value or "").strip()
    parts = cleaned.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return 0.0
    return float(hours * 3600 + minutes * 60 + seconds)


def _build_split_anchor_pack(
    *,
    chunk: dict[str, Any],
    budget: TextMapBudget,
) -> list[dict[str, Any]]:
    source_line_ids = [
        int(item)
        for item in (chunk.get("source_line_ids") or [])
        if str(item).strip()
    ]
    line_texts = [
        str(line).strip()
        for line in str(chunk.get("text", "")).splitlines()
        if str(line).strip()
    ]
    if not source_line_ids:
        line_start = int(chunk.get("line_start", 1) or 1)
        line_end = int(chunk.get("line_end", line_start) or line_start)
        source_line_ids = list(range(line_start, line_end + 1))
    if not line_texts:
        fallback_text = str(chunk.get("text", "")).strip()
        if fallback_text:
            line_texts = [fallback_text]
    if len(line_texts) < len(source_line_ids):
        line_texts.extend([""] * (len(source_line_ids) - len(line_texts)))
    elif len(line_texts) > len(source_line_ids):
        merged_tail = " ".join(line_texts[len(source_line_ids) - 1 :]).strip()
        line_texts = line_texts[: len(source_line_ids) - 1] + [merged_tail]

    timed_lines: list[dict[str, Any]] = []
    start_seconds = _parse_second_precision_timestamp(chunk.get("start_timestamp", ""))
    end_seconds = _parse_second_precision_timestamp(chunk.get("end_timestamp", ""))
    total_span = max(1.0, end_seconds - start_seconds)
    total_lines = max(1, len(source_line_ids))
    for index, (line_id, text) in enumerate(zip(source_line_ids, line_texts, strict=False)):
        line_start_seconds = start_seconds + (total_span * index / total_lines)
        line_end_seconds = start_seconds + (total_span * (index + 1) / total_lines)
        timed_lines.append(
            {
                "line_id": line_id,
                "start_seconds": line_start_seconds,
                "end_seconds": max(line_start_seconds, line_end_seconds),
                "text": text,
            }
        )
    if not timed_lines:
        return []

    target_anchor_count = min(max(1, len(timed_lines)), budget.anchor_limit)
    group_size = max(1, math.ceil(len(timed_lines) / target_anchor_count))
    anchors: list[dict[str, Any]] = []
    for index, start in enumerate(range(0, len(timed_lines), group_size), start=1):
        group = timed_lines[start : start + group_size]
        if not group:
            continue
        evidence_quote = " ".join(str(item.get("text", "")).strip() for item in group).strip()
        if len(evidence_quote) > budget.anchor_quote_chars:
            evidence_quote = evidence_quote[: budget.anchor_quote_chars - 1].rstrip() + "…"
        anchors.append(
            {
                "anchor_id": f"{chunk['chunk_id']}_anc_{index:03d}",
                "modality": "subtitle",
                "source_line_ids": [int(item["line_id"]) for item in group],
                "start_timestamp": format_timestamp_anchor(group[0]["start_seconds"]),
                "end_timestamp": format_timestamp_anchor(group[-1]["end_seconds"]),
                "suggested_screenshot_timestamp": format_timestamp_anchor(group[0]["start_seconds"]),
                "evidence_quote": evidence_quote or f"line {group[0]['line_id']}",
                "confidence": 0.35,
                "candidate_kind": "split_anchor_pack",
            }
        )
        if len(anchors) >= budget.anchor_limit:
            break
    return anchors


def _compact_for_grounding(value: str) -> str:
    compacted = "".join(str(value or "").split())
    for marker in ("\u2026", "..."):
        compacted = compacted.replace(marker, "")
    return compacted


def _quote_grounded_in_anchor(quote: str, anchor_quote: str) -> bool:
    cleaned_quote = str(quote or "").strip()
    cleaned_anchor_quote = str(anchor_quote or "").strip()
    if not cleaned_quote or not cleaned_anchor_quote:
        return False
    if cleaned_quote in cleaned_anchor_quote:
        return True
    compact_quote = _compact_for_grounding(cleaned_quote)
    compact_anchor_quote = _compact_for_grounding(cleaned_anchor_quote)
    return bool(compact_quote and compact_quote in compact_anchor_quote)


def _iter_split_dict_items(raw_items: Any):
    if isinstance(raw_items, dict):
        iterable = raw_items.values()
    elif isinstance(raw_items, (list, tuple)):
        iterable = raw_items
    else:
        return
    for item in iterable:
        if isinstance(item, dict):
            yield item


def _normalize_ref_values(raw_value: Any) -> list[Any]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        return [raw_value]
    if isinstance(raw_value, (list, tuple, set)):
        return list(raw_value)
    return [raw_value]


def _filter_valid_anchor_refs(
    raw_value: Any,
    *,
    anchor_by_id: dict[str, dict[str, Any]],
) -> tuple[list[str], int]:
    valid_refs: list[str] = []
    invalid_count = 0
    for value in _normalize_ref_values(raw_value):
        ref = str(value or "").strip()
        if not ref:
            continue
        if ref in anchor_by_id:
            if ref not in valid_refs:
                valid_refs.append(ref)
        else:
            invalid_count += 1
    return valid_refs, invalid_count


def _first_anchor_quote(
    anchor_ids: list[str],
    *,
    anchor_by_id: dict[str, dict[str, Any]],
) -> str:
    for anchor_id in anchor_ids:
        quote = str(anchor_by_id.get(anchor_id, {}).get("evidence_quote", "") or "").strip()
        if quote:
            return quote
    return ""


def _quote_grounded_in_refs(
    quote: str,
    anchor_ids: list[str],
    *,
    anchor_by_id: dict[str, dict[str, Any]],
) -> bool:
    return any(
        _quote_grounded_in_anchor(
            quote,
            str(anchor_by_id.get(anchor_id, {}).get("evidence_quote", "") or ""),
        )
        for anchor_id in anchor_ids
    )


def _repair_split_map_payload(
    *,
    anchors: list[dict[str, Any]],
    normalized_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    anchor_by_id = {
        str(anchor.get("anchor_id", "") or "").strip(): anchor
        for anchor in anchors
        if isinstance(anchor, dict) and str(anchor.get("anchor_id", "") or "").strip()
    }
    repair_stats = {
        "invalid_atom_anchor_refs": 0,
        "repaired_atom_source_anchor_refs": 0,
        "dropped_atoms_missing_anchor_refs": 0,
        "invalid_relation_anchor_refs": 0,
        "inferred_relation_anchor_refs": 0,
        "relation_quote_backfills": 0,
        "dropped_relations_missing_anchor_refs": 0,
        "dropped_relations_missing_atom_refs": 0,
        "dropped_relations_missing_required_fields": 0,
        "dropped_relations_missing_grounded_quote": 0,
    }

    repaired_atoms: list[dict[str, Any]] = []
    atom_anchor_refs_by_key: dict[str, list[str]] = {}
    for raw_atom in _iter_split_dict_items(normalized_payload.get("atoms")):
        atom = dict(raw_atom)
        valid_refs, invalid_refs = _filter_valid_anchor_refs(
            atom.get("anchor_ids"),
            anchor_by_id=anchor_by_id,
        )
        repair_stats["invalid_atom_anchor_refs"] += invalid_refs

        source_anchor_id = str(atom.get("source_anchor_id", "") or "").strip()
        if source_anchor_id in anchor_by_id:
            if source_anchor_id not in valid_refs:
                valid_refs.insert(0, source_anchor_id)
        elif source_anchor_id:
            repair_stats["invalid_atom_anchor_refs"] += 1
            source_anchor_id = ""

        if not valid_refs:
            repair_stats["dropped_atoms_missing_anchor_refs"] += 1
            continue
        if not source_anchor_id:
            source_anchor_id = valid_refs[0]
            repair_stats["repaired_atom_source_anchor_refs"] += 1

        atom["anchor_ids"] = valid_refs
        atom["source_anchor_id"] = source_anchor_id
        repaired_atoms.append(atom)
        for key in (
            str(atom.get("atom_id", "") or "").strip(),
            str(atom.get("canonical_title", "") or "").strip(),
        ):
            if key:
                atom_anchor_refs_by_key[key] = valid_refs

    repaired_relations: list[dict[str, Any]] = []
    for raw_relation in _iter_split_dict_items(normalized_payload.get("relations")):
        relation = dict(raw_relation)
        source_atom_id = str(relation.get("source_atom_id", "") or "").strip()
        target_atom_id = str(relation.get("target_atom_id", "") or "").strip()
        relation_type = str(relation.get("relation_type", "") or "").strip()
        if not source_atom_id or not target_atom_id or not relation_type:
            repair_stats["dropped_relations_missing_required_fields"] += 1
            continue
        if (
            source_atom_id not in atom_anchor_refs_by_key
            or target_atom_id not in atom_anchor_refs_by_key
        ):
            repair_stats["dropped_relations_missing_atom_refs"] += 1
            continue

        valid_refs, invalid_refs = _filter_valid_anchor_refs(
            relation.get("anchor_ids"),
            anchor_by_id=anchor_by_id,
        )
        repair_stats["invalid_relation_anchor_refs"] += invalid_refs
        if not valid_refs:
            inferred_refs: list[str] = []
            for atom_key in (source_atom_id, target_atom_id):
                for ref in atom_anchor_refs_by_key.get(atom_key, []):
                    if ref not in inferred_refs:
                        inferred_refs.append(ref)
            if inferred_refs:
                valid_refs = inferred_refs
                repair_stats["inferred_relation_anchor_refs"] += 1
        if not valid_refs:
            repair_stats["dropped_relations_missing_anchor_refs"] += 1
            continue

        evidence_quote = str(relation.get("evidence_quote", "") or "").strip()
        if not _quote_grounded_in_refs(
            evidence_quote,
            valid_refs,
            anchor_by_id=anchor_by_id,
        ):
            replacement_quote = _first_anchor_quote(valid_refs, anchor_by_id=anchor_by_id)
            if not replacement_quote:
                repair_stats["dropped_relations_missing_grounded_quote"] += 1
                continue
            relation["evidence_quote"] = replacement_quote
            repair_stats["relation_quote_backfills"] += 1
        else:
            relation["evidence_quote"] = evidence_quote
        relation["anchor_ids"] = valid_refs
        repaired_relations.append(relation)

    return repaired_atoms, repaired_relations, repair_stats


def build_text_atom_relation_prompt(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    chunk: dict[str, Any],
    anchors: list[dict[str, Any]],
    budget: TextMapBudget = DEFAULT_TEXT_MAP_BUDGET,
) -> str:
    profile = select_primary_markdown_profile(
        course_name=course_name,
        lecture_title=lecture_title,
    )
    if profile.primary_profile == "procedural":
        profile_guidance = (
            " 当前 shortform 教学壳为 procedural。"
            " atoms 与 relations 应优先围绕步骤依赖、公式关系、快解路径、易错点组织。"
        )
    elif profile.primary_profile == "conceptual":
        profile_guidance = (
            " 当前 shortform 教学壳为 conceptual。"
            " atoms 与 relations 应优先围绕概念边界、辨析关系、判断规则和错判触发模式组织。"
        )
    else:
        profile_guidance = (
            " 当前 shortform 教学壳为 neutral。"
            " 输出必须保持领域中性，避免默认考试训练口吻。"
        )
    anchor_payload = json.dumps(anchors, ensure_ascii=False, indent=2)
    return (
        "你是通用课程讲义斥候。"
        " 上游已经把单个字幕切片压缩成一组高价值 anchors。"
        f"{profile_guidance}"
        " 你现在只需要基于这些 anchors 生成 chunk_summary、atoms、relations。"
        " 不要重新生成 anchors，不要复述整段字幕。"
        f" chunk_summary 最多 {budget.chunk_summary_sentences} 句，尽量控制在 {budget.chunk_summary_chars} 字以内。"
        f" atoms 最多 {budget.atom_limit} 条，只保留高价值概念、战术、规则、方法或常见误区。"
        " 每条 atom 必须携带 canonical_title、atom_type、summary、body_markdown、anchor_ids、source_anchor_id、status、confidence。"
        f" atom 的 summary 尽量控制在 {budget.atom_summary_chars} 字以内；body_markdown 尽量控制在 {budget.atom_body_chars} 字以内。"
        f" relations 最多 {budget.relation_limit} 条；如果关系不关键或证据不足，宁可返回空数组。"
        " 每条 relation 必须携带 source_atom_id、target_atom_id、relation_type、anchor_ids、evidence_quote、confidence。"
        f" relation 的 evidence_quote 尽量控制在 {budget.relation_quote_chars} 字以内。"
        " 原子与关系只能引用下面给出的 anchor_id。"
        " 禁止输出 anchors、禁止解释性前后缀、禁止 Markdown 代码块，只输出 JSON。"
        f"\n课程名: {course_name}"
        f"\n讲次名: {lecture_title}"
        f"\n来源: {source_url}"
        f"\nChunk ID: {chunk['chunk_id']}"
        f"\n时间范围: {chunk['start_timestamp']} -> {chunk['end_timestamp']}"
        f"\n行号范围: {chunk['line_start']} -> {chunk['line_end']}"
        f"\nAnchor 压缩包:\n{anchor_payload}"
    )


def build_local_qwen_atom_relation_prompt(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    chunk: dict[str, Any],
    anchors: list[dict[str, Any]],
    budget: TextMapBudget = DEFAULT_TEXT_MAP_BUDGET,
) -> str:
    anchor_payload = json.dumps(anchors, ensure_ascii=False, indent=2)
    schema = {
        "chunk_summary": "one sentence grounded in ANCHORS_JSON",
        "atoms": [
            {
                "canonical_title": "concept or method from anchor evidence_quote",
                "atom_type": "concept|method|rule|tactic|pitfall",
                "summary": "short grounded summary",
                "body_markdown": "compact teaching note based only on anchors",
                "anchor_ids": [anchors[0]["anchor_id"] if anchors else ""],
                "source_anchor_id": anchors[0]["anchor_id"] if anchors else "",
                "status": "locked",
                "confidence": 0.8,
            }
        ],
        "relations": [
            {
                "source_atom_id": "atom id or canonical title from atoms",
                "target_atom_id": "atom id or canonical title from atoms",
                "relation_type": "prerequisite|causes|leads_to|contrasts|refines|part_of",
                "anchor_ids": [anchors[0]["anchor_id"] if anchors else ""],
                "evidence_quote": "short exact quote copied from anchor evidence_quote",
                "confidence": 0.8,
            }
        ],
    }
    return (
        "LOCAL_QWEN_MAP_SPLIT_PROFILE_V1\n"
        "Task: extract atoms and relations from already-created subtitle anchors.\n"
        "Use ONLY ANCHORS_JSON. Do not output anchors. Do not explain the schema. Do not invent examples.\n"
        f"Course: {course_name}\n"
        f"Lecture: {lecture_title}\n"
        f"Source: {source_url}\n"
        f"Chunk ID: {chunk['chunk_id']}\n"
        "<ANCHORS_JSON>\n"
        f"{anchor_payload}\n"
        "</ANCHORS_JSON>\n"
        "Grounding rules:\n"
        "- Every atom anchor_ids/source_anchor_id must reference existing anchor_id strings.\n"
        "- Every relation anchor_ids entry must reference existing anchor_id strings.\n"
        "- evidence_quote must be copied from an anchor evidence_quote.\n"
        f"- Return at most {budget.atom_limit} atoms and {budget.relation_limit} relations.\n"
        "- Do not output markdown fences, comments, or prose before/after JSON.\n"
        "OUTPUT_JSON_SCHEMA:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def map_subtitle_chunk(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    chunk: dict[str, Any],
    api_key: str | None = None,
    model: str = DEEPSEEK_MODEL,
    max_concurrent_requests: int = 2,
    telemetry_recorder: RequestRetryTelemetryRecorder | None = None,
    request_label: str = "",
    fast_map_mode: bool = False,
    split_map_mode: bool = False,
    compile_provider: str | None = None,
    source_kind: str = "",
    multimodal_mode: str = "unknown",
) -> tuple[dict[str, Any], dict[str, Any]]:
    budget = FAST_TEXT_MAP_BUDGET if fast_map_mode else DEFAULT_TEXT_MAP_BUDGET
    use_local_qwen_prompt = _local_qwen_provider_requested(compile_provider)
    if split_map_mode:
        anchors = _build_split_anchor_pack(chunk=chunk, budget=budget)
        atom_relation_prompt = (
            build_local_qwen_atom_relation_prompt(
                course_name=course_name,
                lecture_title=lecture_title,
                source_url=source_url,
                chunk=chunk,
                anchors=anchors,
                budget=budget,
            )
            if use_local_qwen_prompt
            else build_text_atom_relation_prompt(
                course_name=course_name,
                lecture_title=lecture_title,
                source_url=source_url,
                chunk=chunk,
                anchors=anchors,
                budget=budget,
            )
        )
        raw_payload, normalized_payload = request_compile_json(
            stage_name="map_split",
            system_prompt=(
                "You are a strict subtitle-grounded JSON extractor."
                if use_local_qwen_prompt
                else "你是严格的课程讲义 JSON 原子/关系斥候。"
            ),
            user_prompt=atom_relation_prompt,
            provider=compile_provider,
            api_key=api_key,
            model=model,
            source_kind=source_kind,
            multimodal_mode=multimodal_mode,
            max_tokens=2048 if fast_map_mode else 3072,
            max_concurrent_requests=max_concurrent_requests,
            telemetry_recorder=telemetry_recorder,
            request_label=request_label or f"map-split:{chunk['chunk_id']}",
            response_schema={"type": "object"},
        )
        repaired_atoms, repaired_relations, split_map_repair = _repair_split_map_payload(
            anchors=anchors,
            normalized_payload=normalized_payload,
        )
        merged_payload = dict(raw_payload)
        merged_payload.update(
            {
                "chunk_summary": str(normalized_payload.get("chunk_summary", "")).strip(),
                "anchors": anchors,
                "atoms": repaired_atoms,
                "relations": repaired_relations,
                "map_mode": "split",
                "split_map_repair": split_map_repair,
                "stage1_payload_size": len(json.dumps(anchors, ensure_ascii=False)),
                "stage2_payload_size": len(atom_relation_prompt),
            }
        )
        return merged_payload, merged_payload
    return request_compile_json(
        stage_name="map",
        system_prompt=(
            "You are a strict subtitle-grounded JSON extractor."
            if use_local_qwen_prompt
            else "你是严格的课程讲义 JSON 斥候。"
        ),
        user_prompt=(
            build_local_qwen_text_map_prompt(
                course_name=course_name,
                lecture_title=lecture_title,
                source_url=source_url,
                chunk=chunk,
                budget=budget,
            )
            if use_local_qwen_prompt
            else build_text_map_prompt(
                course_name=course_name,
                lecture_title=lecture_title,
                source_url=source_url,
                chunk=chunk,
                budget=budget,
            )
        ),
        provider=compile_provider,
        api_key=api_key,
        model=model,
        source_kind=source_kind,
        multimodal_mode=multimodal_mode,
        max_tokens=3072 if fast_map_mode else 8192,
        max_concurrent_requests=max_concurrent_requests,
        telemetry_recorder=telemetry_recorder,
        request_label=request_label or f"map:{chunk['chunk_id']}",
        response_schema={"type": "object"},
    )
