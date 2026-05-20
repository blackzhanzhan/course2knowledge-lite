from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .markdown_support import (
    build_anchor_lookup as _build_anchor_lookup,
    build_atom_lookup as _build_atom_lookup,
    build_default_feedback_routes as _build_default_feedback_routes,
    build_default_followup_scaffold as _build_default_followup_scaffold,
    build_default_minimal_checks as _build_default_minimal_checks,
    build_default_pitfalls as _build_default_pitfalls,
    build_default_review_questions as _build_default_review_questions,
    build_default_search_hooks as _build_default_search_hooks,
    humanize_relation_type as _humanize_relation_type,
    normalize_optional_text as _normalize_optional_text,
    resolve_anchor_label as _resolve_anchor_label,
    resolve_anchor_labels as _resolve_anchor_labels,
    resolve_atom_label as _resolve_atom_label,
)


def _load_json_dict(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object: {path}")
    return payload


def resolve_preferred_dossier_path(artifact_root: Path) -> Path:
    resolved_artifact_root = artifact_root.resolve()
    multimodal_path = (
        resolved_artifact_root / "reduce" / "93_multimodal_dossier.json"
    ).resolve()
    if multimodal_path.is_file():
        return multimodal_path
    return (resolved_artifact_root / "reduce" / "91_lecture_dossier.json").resolve()


def load_preferred_dossier_payload(artifact_root: Path) -> tuple[Path, dict[str, Any]]:
    dossier_path = resolve_preferred_dossier_path(artifact_root)
    payload = _load_json_dict(dossier_path, label="Lecture dossier JSON")
    packet_path = artifact_root.resolve() / "reduce" / "95_exercise_teaching_packet.json"
    if "exercise_teaching_packet" not in payload and packet_path.is_file():
        payload["exercise_teaching_packet"] = _load_json_dict(
            packet_path,
            label="Exercise teaching packet JSON",
        )
    return dossier_path, payload


def _build_visual_embed(
    *,
    anchor_id: str,
    frame_path: str,
    note_path: Path | None,
    image_embed_mode: str,
    obsidian_course_name: str | None,
    lecture_id: str,
) -> str | None:
    normalized_frame_path = str(frame_path).strip()
    if not normalized_frame_path:
        return None
    resolved_frame_path = Path(normalized_frame_path).resolve()
    if image_embed_mode == "obsidian_wiki":
        if not obsidian_course_name:
            return None
        asset_name = f"{str(anchor_id or 'anchor').strip().replace('/', '-')}__{resolved_frame_path.name}"
        vault_relative_path = (
            Path(obsidian_course_name)
            / "_assets"
            / lecture_id
            / asset_name
        )
        return f"![[{vault_relative_path.as_posix()}]]"
    if note_path is None:
        return None
    # Normalize both to plain strings to avoid \\?\ extended-length prefix mismatch on Windows
    frame_str = str(resolved_frame_path)
    note_parent_str = str(note_path.parent.resolve())
    if frame_str.startswith("\\\\?\\"):
        frame_str = frame_str[4:]
    if note_parent_str.startswith("\\\\?\\"):
        note_parent_str = note_parent_str[4:]
    relative_path = os.path.relpath(frame_str, start=note_parent_str)
    return f"![视觉截图]({Path(relative_path).as_posix()})"


def _normalize_formula_lines(formula_candidates: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in formula_candidates:
        expression = str(item.get("expression", "")).strip()
        normalized_expression = str(item.get("normalized_expression", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        confidence = item.get("confidence")
        lead = expression or normalized_expression
        if not lead and not meaning:
            continue
        fragments = []
        if lead:
            fragments.append(f"`{lead}`")
        if meaning:
            fragments.append(meaning)
        if confidence not in (None, ""):
            try:
                fragments.append(f"confidence={float(confidence):.2f}")
            except (TypeError, ValueError):
                pass
        lines.append(" | ".join(fragments))
    return lines


def _build_visual_anchor_payload(
    *,
    anchor: dict[str, Any],
    note_path: Path | None,
    image_embed_mode: str,
    lecture_id: str,
    obsidian_course_name: str | None,
) -> dict[str, Any]:
    anchor_payload = dict(anchor)
    formula_candidates = [
        dict(item)
        for item in anchor_payload.get("formula_candidates") or []
        if isinstance(item, dict)
    ]
    frame_path = _normalize_optional_text(anchor_payload.get("frame_path"))
    ocr_text = _normalize_optional_text(anchor_payload.get("ocr_text"))
    visual_summary = _normalize_optional_text(anchor_payload.get("visual_summary"))
    visual_embed = _build_visual_embed(
        anchor_id=str(anchor_payload.get("anchor_id", "")).strip(),
        frame_path=frame_path,
        note_path=note_path,
        image_embed_mode=image_embed_mode,
        obsidian_course_name=obsidian_course_name,
        lecture_id=lecture_id,
    )
    warning_reasons: list[str] = []
    needs_human_review = bool(anchor_payload.get("needs_human_review", False))
    context_frame_count = int(anchor_payload.get("context_frame_count", 0) or 0)
    if needs_human_review:
        warning_reasons.append("模型已标记该视觉证据需要人工复核。")
    if frame_path and not formula_candidates:
        warning_reasons.append(
            "当前已有截图，但未识别出公式，请人工确认是否存在漏识别。"
        )
    if frame_path and context_frame_count == 1:
        warning_reasons.append(
            "当前视觉证据仅命中单帧，请人工确认关键公式是否已完整捕捉。"
        )
    anchor_payload["formula_candidates"] = formula_candidates
    anchor_payload["visual_summary"] = visual_summary
    anchor_payload["visual_embed"] = visual_embed
    anchor_payload["has_visual_evidence"] = bool(
        frame_path or ocr_text or formula_candidates
    )
    anchor_payload["needs_human_review"] = needs_human_review
    anchor_payload["review_warning_reasons"] = warning_reasons
    anchor_payload["requires_warning_review"] = bool(warning_reasons)
    return anchor_payload


def build_markdown_render_context(
    *,
    course_name: str,
    lecture_id: str,
    lecture_title: str,
    source_url: str,
    provider: str,
    subtitle_source_kind: str,
    artifact_ref: str,
    dossier: dict[str, Any],
    note_path: Path | None = None,
    image_embed_mode: str = "artifact_relative",
    obsidian_course_name: str | None = None,
) -> dict[str, Any]:
    sections = dossier.get("sections") or []
    normalized_anchors = [
        _build_visual_anchor_payload(
            anchor=item,
            note_path=note_path,
            image_embed_mode=image_embed_mode,
            lecture_id=lecture_id,
            obsidian_course_name=obsidian_course_name,
        )
        for item in dossier.get("anchors") or []
        if isinstance(item, dict)
    ]
    atoms = [item for item in dossier.get("atoms") or [] if isinstance(item, dict)]
    relations = [
        item for item in dossier.get("relations") or [] if isinstance(item, dict)
    ]
    atom_exact_lookup, atom_ordinal_lookup = _build_atom_lookup(atoms)
    review_questions = [
        str(item).strip()
        for item in dossier.get("review_questions") or []
        if str(item).strip()
    ] or _build_default_review_questions(
        lecture_summary=str(dossier.get("lecture_summary", "")).strip(),
        sections=[item for item in sections if isinstance(item, dict)],
        atoms=atoms,
        pitfalls=[
            item for item in dossier.get("pitfalls") or [] if isinstance(item, dict)
        ],
    )
    prerequisites = [
        item for item in dossier.get("prerequisites") or [] if isinstance(item, dict)
    ]
    pitfalls = [
        item for item in dossier.get("pitfalls") or [] if isinstance(item, dict)
    ] or _build_default_pitfalls(atoms)
    disambiguation_pairs = [
        item for item in dossier.get("disambiguation_pairs") or [] if isinstance(item, dict)
    ]
    operable_rules = [
        item for item in dossier.get("operable_rules") or [] if isinstance(item, dict)
    ]
    trap_patterns = [
        item for item in dossier.get("trap_patterns") or [] if isinstance(item, dict)
    ]
    minimal_checks = [
        item for item in dossier.get("minimal_checks") or [] if isinstance(item, dict)
    ] or _build_default_minimal_checks(
        review_questions=review_questions,
        atoms=atoms,
    )
    minimal_examples = [
        item
        for item in dossier.get("minimal_examples") or []
        if isinstance(item, dict)
    ]
    followup_scaffold = [
        item
        for item in dossier.get("followup_scaffold") or []
        if isinstance(item, dict)
    ] or _build_default_followup_scaffold(
        atoms=atoms,
        relations=relations,
        review_questions=review_questions,
        atom_exact_lookup=atom_exact_lookup,
        atom_ordinal_lookup=atom_ordinal_lookup,
    )
    feedback_routes = [
        item
        for item in dossier.get("feedback_routes") or []
        if isinstance(item, dict)
    ] or _build_default_feedback_routes(pitfalls)
    search_hooks = [
        item for item in dossier.get("search_hooks") or [] if isinstance(item, dict)
    ] or _build_default_search_hooks(
        course_name=course_name,
        lecture_title=lecture_title,
        atoms=atoms,
        anchors=normalized_anchors,
    )
    return {
        "title": lecture_title,
        "course_name": course_name,
        "lecture_id": lecture_id,
        "source_url": source_url,
        "provider": provider,
        "subtitle_source_kind": subtitle_source_kind,
        "artifact_ref": artifact_ref,
        "dossier_source_path": str(dossier.get("vision_map_path") or "").strip(),
        "lecture_summary": str(dossier.get("lecture_summary", "")).strip(),
        "sections": sections,
        "review_questions": review_questions,
        "atoms": atoms,
        "relations": relations,
        "prerequisites": prerequisites,
        "pitfalls": pitfalls,
        "disambiguation_pairs": disambiguation_pairs,
        "operable_rules": operable_rules,
        "trap_patterns": trap_patterns,
        "minimal_checks": minimal_checks,
        "minimal_examples": minimal_examples,
        "followup_scaffold": followup_scaffold,
        "feedback_routes": feedback_routes,
        "search_hooks": search_hooks,
        "anchors": normalized_anchors,
        "visual_anchors": [
            item for item in normalized_anchors if item.get("has_visual_evidence")
        ],
        "exercise_teaching_packet": dossier.get("exercise_teaching_packet") or {},
    }


def build_markdown_render_context_from_artifact(
    *,
    artifact_root: Path,
    note_path: Path | None,
    image_embed_mode: str,
    obsidian_course_name: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    dossier_path, dossier_payload = load_preferred_dossier_payload(artifact_root)
    context = build_markdown_render_context(
        course_name=str(dossier_payload.get("course_name", "")).strip(),
        lecture_id=str(dossier_payload.get("lecture_id", "")).strip(),
        lecture_title=str(dossier_payload.get("lecture_title", "")).strip(),
        source_url=str(dossier_payload.get("source_url", "")).strip(),
        provider=str(dossier_payload.get("provider", "")).strip(),
        subtitle_source_kind=str(
            dossier_payload.get("subtitle_source_kind", "")
        ).strip(),
        artifact_ref=str(artifact_root.resolve()),
        dossier=dossier_payload,
        note_path=note_path,
        image_embed_mode=image_embed_mode,
        obsidian_course_name=obsidian_course_name,
    )
    context["dossier_source_path"] = str(dossier_path)
    return dossier_path, context


def render_lecture_markdown(context: dict[str, Any]) -> str:
    anchors = context.get("anchors") or []
    if anchors:
        anchor_exact_lookup, anchor_ordinal_lookup = _build_anchor_lookup(anchors)
    else:
        anchor_exact_lookup, anchor_ordinal_lookup = {}, {}
    lines = [
        "---",
        f"title: {context['title']}",
        f"course_name: {context['course_name']}",
        f"lecture_id: {context['lecture_id']}",
        f"source_url: {context['source_url']}",
        f"provider: {context['provider']}",
        f"subtitle_source_kind: {context['subtitle_source_kind']}",
        f"artifact_ref: {context['artifact_ref']}",
        "status: draft",
        "---",
        "",
        f"# {context['title']}",
        "",
    ]
    lecture_summary = str(context.get("lecture_summary", "")).strip()
    if lecture_summary:
        lines.extend(["## 总摘要", lecture_summary, ""])
    exercise_packet = context.get("exercise_teaching_packet") or {}
    if isinstance(exercise_packet, dict) and exercise_packet:
        lines.extend(_render_exercise_teaching_packet_lines(exercise_packet))
    prerequisites = [
        item for item in context.get("prerequisites") or [] if isinstance(item, dict)
    ]
    if prerequisites:
        lines.append("## 前置知识")
        for item in prerequisites:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            line = f"- **{title}**"
            why_it_matters = str(item.get("why_it_matters", "")).strip()
            if why_it_matters:
                line += f"：{why_it_matters}"
            lines.append(line)
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    for section in context.get("sections") or []:
        heading = str(section.get("heading", "")).strip()
        body = str(section.get("body", "")).strip()
        if not heading:
            continue
        lines.extend([f"## {heading}", body or "（待补）", ""])
    review_questions = [
        str(item).strip()
        for item in context.get("review_questions") or []
        if str(item).strip()
    ]
    if review_questions:
        lines.append("## 复习问题")
        lines.extend(f"- {item}" for item in review_questions)
        lines.append("")
    if anchors:
        lines.append("## 证据锚点")
        for anchor in anchors:
            lines.append(
                "- "
                f"锚点：`{anchor['anchor_id']}` | "
                f"[{anchor['start_timestamp']} -> {anchor['end_timestamp']}] "
                f"Line IDs: {','.join(str(item) for item in anchor.get('source_line_ids', []))} | "
                f"{anchor['evidence_quote']}"
            )
        lines.append("")
    atoms = [
        atom for atom in context.get("atoms") or [] if isinstance(atom, dict)
    ]
    atom_exact_lookup, atom_ordinal_lookup = _build_atom_lookup(atoms)
    if atoms:
        lines.append("## 知识原子")
        for atom in atoms:
            title = str(atom.get("canonical_title", "")).strip() or str(
                atom.get("atom_id", "")
            ).strip()
            if not title:
                continue
            lines.extend([f"### {title}"])
            atom_type = str(atom.get("atom_type", "")).strip()
            if atom_type:
                lines.append(f"- 类型：{atom_type}")
            summary = str(atom.get("summary", "")).strip()
            if summary:
                lines.append(f"- 摘要：{summary}")
            status = str(atom.get("status", "")).strip()
            confidence = atom.get("confidence")
            meta_fragments: list[str] = []
            if status:
                meta_fragments.append(f"status={status}")
            if confidence not in (None, ""):
                try:
                    meta_fragments.append(f"confidence={float(confidence):.2f}")
                except (TypeError, ValueError):
                    pass
            if meta_fragments:
                lines.append(f"- 元信息：{' | '.join(meta_fragments)}")
            resolved_anchor_labels = _resolve_anchor_labels(
                list(atom.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if resolved_anchor_labels:
                lines.append(f"- 证据锚点：{', '.join(f'`{label}`' for label in resolved_anchor_labels)}")
            source_anchor_label = _resolve_anchor_label(
                atom.get("source_anchor_id"),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if source_anchor_label:
                lines.append(f"- 主锚点：`{source_anchor_label}`")
            body = str(atom.get("body_markdown", "")).strip()
            if body:
                lines.extend(["", body])
            lines.append("")
    relations = [
        relation
        for relation in context.get("relations") or []
        if isinstance(relation, dict)
    ]
    if relations:
        lines.append("## 知识关系")
        for relation in relations:
            source_label = _resolve_atom_label(
                relation.get("source_atom_id"),
                exact_lookup=atom_exact_lookup,
                ordinal_lookup=atom_ordinal_lookup,
            )
            target_label = _resolve_atom_label(
                relation.get("target_atom_id"),
                exact_lookup=atom_exact_lookup,
                ordinal_lookup=atom_ordinal_lookup,
            )
            relation_type = str(relation.get("relation_type", "")).strip()
            relation_header = (
                f"`{source_label or relation.get('source_atom_id', '')}` "
                f"--{relation_type or 'related_to'}--> "
                f"`{target_label or relation.get('target_atom_id', '')}`"
            )
            lines.append(f"- {relation_header}")
            evidence_quote = str(relation.get("evidence_quote", "")).strip()
            if evidence_quote:
                lines.append(f"  证据：{evidence_quote}")
            resolved_anchor_labels = _resolve_anchor_labels(
                list(relation.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if resolved_anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in resolved_anchor_labels)
                )
            confidence = relation.get("confidence")
            if confidence not in (None, ""):
                try:
                    lines.append(f"  confidence={float(confidence):.2f}")
                except (TypeError, ValueError):
                    pass
        lines.append("")
    disambiguation_pairs = [
        item for item in context.get("disambiguation_pairs") or [] if isinstance(item, dict)
    ]
    if disambiguation_pairs:
        lines.append("## 易混辨析")
        for item in disambiguation_pairs:
            left = str(item.get("left", "")).strip()
            right = str(item.get("right", "")).strip()
            difference = str(item.get("difference", "")).strip()
            if not left or not right:
                continue
            lines.append(f"- `辨析对`：**{left}** vs **{right}**")
            if difference:
                lines.append(f"  区分要点：{difference}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    operable_rules = [
        item for item in context.get("operable_rules") or [] if isinstance(item, dict)
    ]
    if operable_rules:
        lines.append("## 判断规则")
        for item in operable_rules:
            condition = str(item.get("condition", "")).strip()
            judgment = str(item.get("judgment", "")).strip()
            if not condition or not judgment:
                continue
            lines.append(f"- 条件：{condition}")
            lines.append(f"  判断：{judgment}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    pitfalls = [
        item for item in context.get("pitfalls") or [] if isinstance(item, dict)
    ]
    if pitfalls:
        lines.append("## 易错提醒")
        for item in pitfalls:
            title = str(item.get("title", "")).strip()
            summary = str(item.get("why_wrong", "")).strip()
            body = str(item.get("correction", "")).strip()
            if not title:
                continue
            lines.append(f"- `误区/反例`：**{title}**")
            if summary:
                lines.append(f"  概述：{summary}")
            if body:
                lines.append(f"  展开：{body}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    trap_patterns = [
        item for item in context.get("trap_patterns") or [] if isinstance(item, dict)
    ]
    if trap_patterns:
        lines.append("## 高频错判")
        for item in trap_patterns:
            trigger = str(item.get("trigger", "")).strip()
            wrong_outcome = str(item.get("wrong_outcome", "")).strip()
            correction = str(item.get("correction", "")).strip()
            if not trigger or not wrong_outcome:
                continue
            lines.append(f"- 触发：{trigger}")
            lines.append(f"  错判：{wrong_outcome}")
            if correction:
                lines.append(f"  修正：{correction}")
        lines.append("")
    minimal_examples = [
        item
        for item in context.get("minimal_examples") or []
        if isinstance(item, dict)
    ]
    if minimal_examples:
        lines.append("## 最小例题")
        for item in minimal_examples:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            lines.append(f"### {title}")
            problem = str(item.get("problem", "")).strip()
            if problem:
                lines.append(f"- 题干：{problem}")
            steps = [
                str(step).strip()
                for step in item.get("steps") or []
                if str(step).strip()
            ]
            if steps:
                lines.append("- 步骤：")
                for step_index, step in enumerate(steps, start=1):
                    lines.append(f"  {step_index}. {step}")
            takeaway = str(item.get("takeaway", "")).strip()
            if takeaway:
                lines.append(f"- 收束：{takeaway}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
            lines.append("")
    minimal_checks = [
        item for item in context.get("minimal_checks") or [] if isinstance(item, dict)
    ]
    if minimal_checks:
        lines.append("## 最小抽问")
        for item in minimal_checks:
            prompt = str(item.get("prompt", "")).strip()
            expected_focus = str(item.get("expected_focus", "")).strip()
            if not prompt:
                continue
            lines.append(f"- 抽问：{prompt}")
            if expected_focus:
                lines.append(f"  过线标准：{expected_focus}")
        lines.append("")
    followup_scaffold = [
        item
        for item in context.get("followup_scaffold") or []
        if isinstance(item, dict)
    ]
    if followup_scaffold:
        lines.append("## 追问脚手架")
        for item in followup_scaffold:
            target = str(item.get("target", "")).strip()
            if not target:
                continue
            lines.append(f"- 追问目标：**{target}**")
            probe_focus = str(item.get("probe_focus", "")).strip()
            if probe_focus:
                lines.append(f"  先问什么：{probe_focus}")
            escalation_rule = str(item.get("escalation_rule", "")).strip()
            if escalation_rule:
                lines.append(f"  若答错如何转向：{escalation_rule}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    feedback_routes = [
        item
        for item in context.get("feedback_routes") or []
        if isinstance(item, dict)
    ]
    if feedback_routes:
        lines.append("## 答错分流")
        for item in feedback_routes:
            trigger = str(item.get("trigger", "")).strip()
            if not trigger:
                continue
            lines.append(f"- 触发：**{trigger}**")
            diagnosis = str(item.get("diagnosis", "")).strip()
            if diagnosis:
                lines.append(f"  诊断：{diagnosis}")
            next_step = str(item.get("next_step", "")).strip()
            if next_step:
                lines.append(f"  下一步：{next_step}")
            anchor_labels = _resolve_anchor_labels(
                list(item.get("anchor_ids") or []),
                exact_lookup=anchor_exact_lookup,
                ordinal_lookup=anchor_ordinal_lookup,
            )
            if anchor_labels:
                lines.append(
                    "  锚点："
                    + ", ".join(f"`{label}`" for label in anchor_labels)
                )
        lines.append("")
    search_hooks = [
        item for item in context.get("search_hooks") or [] if isinstance(item, dict)
    ]
    if search_hooks:
        lines.append("## 外搜钩子")
        for item in search_hooks:
            query = str(item.get("query", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if not query:
                continue
            line = f"- `{query}`"
            if reason:
                line += f"：{reason}"
            lines.append(line)
        lines.append("")
    visual_anchors = context.get("visual_anchors") or []
    if visual_anchors:
        lines.append("## 视觉补注")
        for anchor in visual_anchors:
            if anchor.get("requires_warning_review"):
                warning_header = f"> [!warning] 人工复核 · {anchor['start_timestamp']} - {anchor['end_timestamp']}"
                lines.append(warning_header)
                lines.append(f"> 锚点：`{anchor['anchor_id']}`")
                for reason in anchor.get("review_warning_reasons") or []:
                    lines.append(f"> - {reason}")
                lines.append("")
            header = f"> [!info] 视觉补注 · {anchor['start_timestamp']} - {anchor['end_timestamp']}"
            lines.append(header)
            lines.append(f"> 锚点：`{anchor['anchor_id']}`")
            lines.append(f"> 字幕证据：{anchor['evidence_quote']}")
            visual_embed = _normalize_optional_text(anchor.get("visual_embed", ""))
            if visual_embed:
                lines.append(f"> {visual_embed}")
            visual_summary = _normalize_optional_text(anchor.get("visual_summary", ""))
            if visual_summary:
                lines.append(f"> 视觉摘要：{visual_summary}")
            ocr_text = _normalize_optional_text(anchor.get("ocr_text", ""))
            if ocr_text:
                lines.append("> OCR 摘录：")
                for ocr_line in ocr_text.splitlines() or [ocr_text]:
                    stripped_line = ocr_line.strip()
                    if stripped_line:
                        lines.append(f"> {stripped_line}")
            formula_lines = _normalize_formula_lines(
                list(anchor.get("formula_candidates") or [])
            )
            if formula_lines:
                lines.append("> 公式候选：")
                for formula_line in formula_lines:
                    lines.append(f"> - {formula_line}")
            lines.append("")
    return "\n".join(lines)


def _render_exercise_teaching_packet_lines(packet: dict[str, Any]) -> list[str]:
    lines = ["## Exercise Teaching Packet"]
    status = str(packet.get("status", "")).strip()
    if status:
        lines.append(f"- status: `{status}`")
    if not packet.get("teaching_allowed", False):
        lines.append("- confirmed_teaching: blocked pending review")
    question_stem = str(packet.get("question_stem", "")).strip()
    if question_stem:
        lines.extend(["", "### Question Stem", question_stem])
    conditions = [
        str(item).strip()
        for item in packet.get("conditions") or []
        if str(item).strip()
    ]
    if conditions:
        lines.extend(["", "### Conditions"])
        lines.extend(f"- {item}" for item in conditions)
    ask = str(packet.get("ask", "")).strip()
    if ask:
        lines.extend(["", "### Ask", ask])
    solving_entry = str(packet.get("solving_entry", "")).strip()
    if solving_entry:
        lines.extend(["", "### Solving Entry", solving_entry])
    steps = [item for item in packet.get("step_skeleton") or [] if isinstance(item, dict)]
    if steps:
        lines.extend(["", "### Step Skeleton"])
        for item in steps:
            index = item.get("index", "")
            action = str(item.get("action", "")).strip()
            if action:
                lines.append(f"- {index}. {action}")
    trap = packet.get("trap") or {}
    if isinstance(trap, dict) and any(str(value).strip() for value in trap.values()):
        lines.extend(["", "### Trap"])
        for key in ("title", "why_wrong", "correction"):
            value = str(trap.get(key, "")).strip()
            if value:
                lines.append(f"- {key}: {value}")
    variant = packet.get("variant_check") or {}
    if isinstance(variant, dict):
        prompt = str(variant.get("prompt", "")).strip()
        if prompt:
            lines.extend(["", "### Variant Check", prompt])
    conflicts = [item for item in packet.get("conflicts") or [] if isinstance(item, dict)]
    blockers = [
        item for item in packet.get("review_blockers") or [] if isinstance(item, dict)
    ]
    if conflicts or blockers:
        lines.extend(["", "### Review Gate"])
        for item in conflicts:
            reason = str(item.get("type", "")).strip() or "conflict"
            lines.append(f"- conflict: {reason}")
        for item in blockers:
            reason = str(item.get("code", "")).strip() or "review_required"
            message = str(item.get("message", "")).strip()
            lines.append(f"- blocker: {reason}" + (f" - {message}" if message else ""))
    lines.append("")
    return lines


def build_entity_candidates_payload(
    *,
    course_name: str,
    lecture_title: str,
    source_url: str,
    lecture_id: str,
    atoms: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "lecture_id": lecture_id,
        "course_name": course_name,
        "lecture_title": lecture_title,
        "source_url": source_url,
        "status": "candidate",
        "atoms": atoms,
        "relations": relations,
    }
