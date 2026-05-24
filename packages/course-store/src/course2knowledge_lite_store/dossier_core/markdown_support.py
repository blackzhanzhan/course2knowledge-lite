from __future__ import annotations

from typing import Any


PITFALL_KEYWORDS = ("误区", "误导", "陷阱", "毒药", "反例", "易错", "错误")


def build_anchor_lookup(
    anchors: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    exact_lookup: dict[str, dict[str, Any]] = {}
    ordinal_lookup: dict[str, dict[str, Any]] = {}
    for index, anchor in enumerate(anchors, start=1):
        anchor_id = str(anchor.get("anchor_id", "")).strip()
        if anchor_id:
            exact_lookup[anchor_id] = anchor
        ordinal_lookup[str(index)] = anchor
    return exact_lookup, ordinal_lookup


def resolve_anchor_label(
    raw_anchor_id: Any,
    *,
    exact_lookup: dict[str, dict[str, Any]],
    ordinal_lookup: dict[str, dict[str, Any]],
) -> str:
    normalized = str(raw_anchor_id or "").strip()
    if not normalized:
        return ""
    anchor = exact_lookup.get(normalized) or ordinal_lookup.get(normalized)
    if anchor is None:
        return normalized
    anchor_id = str(anchor.get("anchor_id", "")).strip() or normalized
    start_timestamp = str(anchor.get("start_timestamp", "")).strip()
    end_timestamp = str(anchor.get("end_timestamp", "")).strip()
    if start_timestamp and end_timestamp:
        return f"{anchor_id} ({start_timestamp} -> {end_timestamp})"
    return anchor_id


def resolve_anchor_labels(
    raw_anchor_ids: list[Any] | tuple[Any, ...],
    *,
    exact_lookup: dict[str, dict[str, Any]],
    ordinal_lookup: dict[str, dict[str, Any]],
) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for raw_anchor_id in raw_anchor_ids:
        label = resolve_anchor_label(
            raw_anchor_id,
            exact_lookup=exact_lookup,
            ordinal_lookup=ordinal_lookup,
        )
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def build_atom_lookup(
    atoms: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    exact_lookup: dict[str, dict[str, Any]] = {}
    ordinal_lookup: dict[str, dict[str, Any]] = {}
    for index, atom in enumerate(atoms, start=1):
        atom_id = str(atom.get("atom_id", "")).strip()
        canonical_title = str(atom.get("canonical_title", "")).strip()
        if atom_id:
            exact_lookup[atom_id] = atom
        if canonical_title:
            exact_lookup.setdefault(canonical_title, atom)
        ordinal_lookup[str(index)] = atom
    return exact_lookup, ordinal_lookup


def resolve_atom_label(
    raw_atom_id: Any,
    *,
    exact_lookup: dict[str, dict[str, Any]],
    ordinal_lookup: dict[str, dict[str, Any]],
) -> str:
    normalized = str(raw_atom_id or "").strip()
    if not normalized:
        return ""
    atom = exact_lookup.get(normalized) or ordinal_lookup.get(normalized)
    if atom is None:
        return normalized
    return (
        str(atom.get("canonical_title", "")).strip()
        or str(atom.get("atom_id", "")).strip()
        or normalized
    )


def humanize_relation_type(raw_relation_type: str) -> str:
    mapping = {
        "prerequisite": "作为前提",
        "prerequisite_of": "作为前提",
        "prerequisite_for": "作为前提",
        "applies_to": "适用于",
        "applies_when": "适用条件",
        "contrasts": "形成对比",
        "contrasts_with": "形成对比",
        "solves": "用于解决",
        "guides": "指导",
        "part_of": "属于组成部分",
        "influences": "影响",
    }
    normalized = str(raw_relation_type or "").strip().lower()
    return mapping.get(normalized, str(raw_relation_type or "").strip() or "相关")


def build_pitfall_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        title = str(atom.get("canonical_title", "")).strip()
        atom_type = str(atom.get("atom_type", "")).strip()
        combined = " ".join(
            [
                title,
                atom_type,
                str(atom.get("summary", "")).strip(),
                str(atom.get("body_markdown", "")).strip(),
            ]
        )
        if not any(keyword in combined for keyword in PITFALL_KEYWORDS):
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)
        selected.append(atom)
    return selected


def build_default_followup_scaffold(
    *,
    atoms: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    review_questions: list[str],
    atom_exact_lookup: dict[str, dict[str, Any]],
    atom_ordinal_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(target: str, probe_focus: str, escalation_rule: str) -> None:
        normalized_target = str(target).strip()
        if not normalized_target or normalized_target in seen:
            return
        seen.add(normalized_target)
        items.append(
            {
                "target": normalized_target,
                "probe_focus": probe_focus,
                "escalation_rule": escalation_rule,
                "anchor_ids": [],
            }
        )

    for question in review_questions:
        add(
            question,
            "先判断用户是否只会复述结论，再追问依据和前提。",
            "若用户答不出，回到对应知识原子或证据锚点重讲。",
        )
    for atom in atoms[:6]:
        title = str(atom.get("canonical_title", "")).strip()
        if not title:
            continue
        add(
            title,
            "先问定义，再问前提，再问如果理解反了会错在哪里。",
            "若定义不稳，回到前置知识；若迁移失败，转去最小例题。",
        )
    for relation in relations[:4]:
        source_label = resolve_atom_label(
            relation.get("source_atom_id"),
            exact_lookup=atom_exact_lookup,
            ordinal_lookup=atom_ordinal_lookup,
        )
        target_label = resolve_atom_label(
            relation.get("target_atom_id"),
            exact_lookup=atom_exact_lookup,
            ordinal_lookup=atom_ordinal_lookup,
        )
        relation_phrase = humanize_relation_type(
            str(relation.get("relation_type", "")).strip()
        )
        if source_label and target_label:
            add(
                f"{source_label} -> {target_label}",
                f"追问为什么「{source_label}」会{relation_phrase}「{target_label}」。",
                "若关系理解不清，分别回到两个知识原子，再重建联系。",
            )
    for atom in build_pitfall_atoms(atoms)[:4]:
        title = str(atom.get("canonical_title", "")).strip()
        if title:
            add(
                title,
                "先追问为什么它看起来像对的，再追问它为什么其实是误区。",
                "若用户反复踩坑，转入答错分流并回到反例解释。",
            )
    return items[:12]


def build_default_review_questions(
    *,
    lecture_summary: str,
    sections: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    pitfalls: list[dict[str, Any]],
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(question: str) -> None:
        normalized = str(question).strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        items.append(normalized)

    summary_text = str(lecture_summary or "").strip()
    if summary_text:
        add("本讲的主线是什么？")
    for atom in atoms[:3]:
        title = str(atom.get("canonical_title", "")).strip()
        if title:
            add(f"什么是「{title}」？")
    for section in sections[:2]:
        heading = str(section.get("heading", "")).strip()
        if heading:
            add(f"「{heading}」这一部分最重要的判断是什么？")
    for item in pitfalls[:2]:
        title = str(item.get("title", "")).strip()
        if title:
            add(f"为什么不能把「{title}」当成正确理解？")
    return items[:6]


def build_default_minimal_checks(
    *,
    review_questions: list[str],
    atoms: list[dict[str, Any]],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_prompts: set[str] = set()

    def add(prompt: str, expected_focus: str) -> None:
        normalized_prompt = str(prompt).strip()
        if not normalized_prompt or normalized_prompt in seen_prompts:
            return
        seen_prompts.add(normalized_prompt)
        items.append(
            {
                "prompt": normalized_prompt,
                "expected_focus": str(expected_focus).strip(),
            }
        )

    for question in review_questions[:3]:
        add(
            question,
            "先答定义或结论，再补充判断依据、适用前提或反例。",
        )
    for atom in atoms[:2]:
        title = str(atom.get("canonical_title", "")).strip()
        if title:
            add(
                f"如果把「{title}」说反了，会错在哪里？",
                "要指出概念边界，并说明最容易混淆的错判点。",
            )
    return items[:5]


def build_default_search_hooks(
    *,
    course_name: str,
    lecture_title: str,
    atoms: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
) -> list[dict[str, str]]:
    hooks: list[dict[str, str]] = []
    seen_queries: set[str] = set()

    def add(query: str, reason: str) -> None:
        normalized_query = str(query).strip()
        if not normalized_query or normalized_query in seen_queries:
            return
        seen_queries.add(normalized_query)
        hooks.append({"query": normalized_query, "reason": reason})

    for atom in atoms[:8]:
        title = str(atom.get("canonical_title", "")).strip()
        if not title:
            continue
        add(f'"{title}"', "讲内核心知识原子")
        add(f'"{course_name}" "{title}"', "课程名与知识原子联合检索")
        combined = " ".join(
            [
                str(atom.get("atom_type", "")).strip(),
                str(atom.get("summary", "")).strip(),
                str(atom.get("body_markdown", "")).strip(),
            ]
        )
        if combined and any(keyword in combined for keyword in PITFALL_KEYWORDS):
            add(f'"{title}" 易错点', "讲内误区/反例原子")
    for anchor in anchors:
        for item in anchor.get("formula_candidates") or []:
            if not isinstance(item, dict):
                continue
            expression = (
                str(item.get("normalized_expression", "")).strip()
                or str(item.get("expression", "")).strip()
            )
            if expression:
                add(f'"{expression}"', "讲内公式候选")
                add(f'"{course_name}" "{expression}"', "课程名与公式候选联合检索")
    add(f'"{lecture_title}"', "讲次标题精确检索")
    add(f'"{course_name}" "{lecture_title}"', "课程名与讲次名联合检索")
    return hooks[:12]


def build_default_pitfalls(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for atom in build_pitfall_atoms(atoms):
        items.append(
            {
                "title": str(atom.get("canonical_title", "")).strip(),
                "why_wrong": str(atom.get("summary", "")).strip(),
                "correction": str(atom.get("body_markdown", "")).strip(),
                "anchor_ids": list(atom.get("anchor_ids") or []),
            }
        )
    return items


def build_default_feedback_routes(
    pitfalls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in pitfalls[:6]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        items.append(
            {
                "trigger": f"用户掉进「{title}」",
                "diagnosis": str(item.get("why_wrong", "")).strip(),
                "next_step": str(item.get("correction", "")).strip(),
                "anchor_ids": list(item.get("anchor_ids") or []),
            }
        )
    return items


def normalize_optional_text(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip()
    if normalized.lower() in {"none", "null"}:
        return ""
    return normalized
