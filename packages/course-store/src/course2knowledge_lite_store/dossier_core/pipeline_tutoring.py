from __future__ import annotations

from typing import Any

from .contracts import normalize_anchor_ids
from .course_profiles import select_primary_markdown_profile


def truncate_text(raw_value: Any, *, limit: int = 160) -> str:
    normalized = str(raw_value or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "…"


def ensure_minimal_examples(
    minimal_examples: list[dict[str, Any]],
    *,
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if minimal_examples:
        return minimal_examples
    if not atoms:
        return []
    first_atom = atoms[0]
    anchor_ids = list(normalize_anchor_ids(first_atom.get("anchor_ids")))
    return [
        {
            "title": str(first_atom.get("canonical_title", "")).strip() or "最小例题",
            "problem": truncate_text(first_atom.get("summary", "")),
            "steps": [
                "先确认题目里的已知量与未知量。",
                "再根据讲内原子与关系组织解题步骤。",
            ],
            "takeaway": truncate_text(first_atom.get("body_markdown", "")),
            "anchor_ids": anchor_ids,
        }
    ]


def derive_pitfalls_from_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for atom in atoms:
        title = str(atom.get("canonical_title", "")).strip()
        combined = " ".join(
            [
                str(atom.get("atom_type", "")).strip(),
                str(atom.get("summary", "")).strip(),
                str(atom.get("body_markdown", "")).strip(),
            ]
        )
        if not title or title in seen_titles:
            continue
        if not any(
            keyword in combined
            for keyword in ("误区", "误导", "陷阱", "毒药", "反例", "易错", "错误")
        ):
            continue
        seen_titles.add(title)
        items.append(
            {
                "title": title,
                "why_wrong": truncate_text(atom.get("summary", "")),
                "correction": truncate_text(atom.get("body_markdown", "")),
                "anchor_ids": list(normalize_anchor_ids(atom.get("anchor_ids"))),
            }
        )
    return items


def derive_conceptual_disambiguation_pairs(
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left, right in zip(atoms, atoms[1:], strict=False):
        left_title = str(left.get("canonical_title", "")).strip()
        right_title = str(right.get("canonical_title", "")).strip()
        if not left_title or not right_title or left_title == right_title:
            continue
        difference = truncate_text(
            str(left.get("summary", "")).strip()
            or str(right.get("summary", "")).strip()
            or str(left.get("body_markdown", "")).strip()
            or str(right.get("body_markdown", "")).strip(),
            limit=120,
        )
        pairs.append(
            {
                "left": left_title,
                "right": right_title,
                "difference": difference,
                "anchor_ids": list(
                    normalize_anchor_ids(
                        list(left.get("anchor_ids") or [])
                        + list(right.get("anchor_ids") or [])
                    )
                ),
            }
        )
        if len(pairs) >= 3:
            break
    return pairs


def derive_conceptual_operable_rules(
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for atom in atoms[:4]:
        title = str(atom.get("canonical_title", "")).strip()
        summary = truncate_text(
            str(atom.get("summary", "")).strip()
            or str(atom.get("body_markdown", "")).strip(),
            limit=120,
        )
        if not title or not summary:
            continue
        rules.append(
            {
                "condition": f"如果题干或表述落在“{title}”上",
                "judgment": summary,
                "anchor_ids": list(normalize_anchor_ids(atom.get("anchor_ids"))),
            }
        )
    return rules


def derive_trap_patterns_from_pitfalls(
    pitfalls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for item in pitfalls[:4]:
        title = str(item.get("title", "")).strip()
        why_wrong = str(item.get("why_wrong", "")).strip()
        correction = str(item.get("correction", "")).strip()
        if not title or not why_wrong:
            continue
        patterns.append(
            {
                "trigger": title,
                "wrong_outcome": why_wrong,
                "correction": correction,
                "anchor_ids": list(normalize_anchor_ids(item.get("anchor_ids"))),
            }
        )
    return patterns


def derive_minimal_checks(
    review_questions: list[str],
    *,
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for question in review_questions[:4]:
        normalized = str(question).strip()
        if not normalized:
            continue
        checks.append(
            {
                "prompt": normalized,
                "expected_focus": "必须回到正文中的核心命题作答，不可泛泛复述。",
                "anchor_ids": [],
            }
        )
    if not checks:
        for atom in atoms[:3]:
            title = str(atom.get("canonical_title", "")).strip()
            if not title:
                continue
            checks.append(
                {
                    "prompt": f"请用一句话说明“{title}”的核心判断口径。",
                    "expected_focus": "必须指出该概念/规则最关键的判断边界。",
                    "anchor_ids": list(normalize_anchor_ids(atom.get("anchor_ids"))),
                }
            )
    return checks


def enrich_tutoring_fields(
    *,
    tutoring_payload: dict[str, Any],
    course_name: str,
    lecture_title: str,
    atoms: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched = dict(tutoring_payload)
    profile = select_primary_markdown_profile(
        course_name=course_name,
        lecture_title=lecture_title,
    )
    atom_lookup: dict[str, dict[str, Any]] = {}
    for index, atom in enumerate(atoms, start=1):
        atom_id = str(atom.get("atom_id", "")).strip()
        title = str(atom.get("canonical_title", "")).strip()
        if atom_id:
            atom_lookup[atom_id] = atom
        if title:
            atom_lookup.setdefault(title, atom)
        atom_lookup.setdefault(str(index), atom)

    prerequisites = list(enriched.get("prerequisites") or [])
    seen_prerequisites = {
        str(item.get("title", "")).strip()
        for item in prerequisites
        if isinstance(item, dict)
    }
    for atom in atoms:
        title = str(atom.get("canonical_title", "")).strip()
        if not title or title in seen_prerequisites:
            continue
        prerequisites.append(
            {
                "title": title,
                "why_it_matters": truncate_text(
                    atom.get("summary") or atom.get("body_markdown") or ""
                ),
                "anchor_ids": list(normalize_anchor_ids(atom.get("anchor_ids"))),
            }
        )
        seen_prerequisites.add(title)
        if len(prerequisites) >= 3:
            break
    enriched["prerequisites"] = prerequisites

    pitfalls = list(enriched.get("pitfalls") or [])
    seen_pitfalls = {
        str(item.get("title", "")).strip()
        for item in pitfalls
        if isinstance(item, dict)
    }
    for item in derive_pitfalls_from_atoms(atoms):
        title = str(item.get("title", "")).strip()
        if title in seen_pitfalls:
            continue
        pitfalls.append(item)
        seen_pitfalls.add(title)
    enriched["pitfalls"] = pitfalls

    enriched["minimal_examples"] = ensure_minimal_examples(
        list(enriched.get("minimal_examples") or []),
        atoms=atoms,
    )
    if profile.primary_profile == "conceptual":
        disambiguation_pairs = list(enriched.get("disambiguation_pairs") or [])
        if not disambiguation_pairs:
            disambiguation_pairs = derive_conceptual_disambiguation_pairs(atoms)
        enriched["disambiguation_pairs"] = disambiguation_pairs

        operable_rules = list(enriched.get("operable_rules") or [])
        if not operable_rules:
            operable_rules = derive_conceptual_operable_rules(atoms)
        enriched["operable_rules"] = operable_rules

        trap_patterns = list(enriched.get("trap_patterns") or [])
        if not trap_patterns:
            trap_patterns = derive_trap_patterns_from_pitfalls(pitfalls)
        enriched["trap_patterns"] = trap_patterns

        minimal_checks = list(enriched.get("minimal_checks") or [])
        if not minimal_checks:
            minimal_checks = derive_minimal_checks(
                list(enriched.get("review_questions") or []),
                atoms=atoms,
            )
        enriched["minimal_checks"] = minimal_checks

    followup_scaffold = list(enriched.get("followup_scaffold") or [])
    seen_scaffold_targets = {
        str(item.get("target", "")).strip()
        for item in followup_scaffold
        if isinstance(item, dict)
    }
    for atom in atoms:
        title = str(atom.get("canonical_title", "")).strip()
        if not title or title in seen_scaffold_targets:
            continue
        followup_scaffold.append(
            {
                "target": title,
                "probe_focus": "先问定义，再问前提，再问如果理解反了会错在哪里。",
                "escalation_rule": "若用户答不出，回到前置知识或最小例题重讲。",
                "anchor_ids": list(normalize_anchor_ids(atom.get("anchor_ids"))),
            }
        )
        seen_scaffold_targets.add(title)
        if len(followup_scaffold) >= 8:
            break
    if len(followup_scaffold) < 8:
        for relation in relations:
            source_atom = atom_lookup.get(str(relation.get("source_atom_id", "")).strip())
            target_atom = atom_lookup.get(str(relation.get("target_atom_id", "")).strip())
            source_title = (
                str((source_atom or {}).get("canonical_title", "")).strip()
                or str(relation.get("source_atom_id", "")).strip()
            )
            target_title = (
                str((target_atom or {}).get("canonical_title", "")).strip()
                or str(relation.get("target_atom_id", "")).strip()
            )
            target = f"{source_title} -> {target_title}"
            if not source_title or not target_title or target in seen_scaffold_targets:
                continue
            followup_scaffold.append(
                {
                    "target": target,
                    "probe_focus": "追问两者为什么相关，以及如果倒过来理解会错在哪里。",
                    "escalation_rule": "若关系答不清，分别回到两个知识原子再重建联系。",
                    "anchor_ids": list(normalize_anchor_ids(relation.get("anchor_ids"))),
                }
            )
            seen_scaffold_targets.add(target)
            if len(followup_scaffold) >= 8:
                break
    enriched["followup_scaffold"] = followup_scaffold

    feedback_routes = list(enriched.get("feedback_routes") or [])
    seen_feedback_triggers = {
        str(item.get("trigger", "")).strip()
        for item in feedback_routes
        if isinstance(item, dict)
    }
    for item in pitfalls:
        title = str(item.get("title", "")).strip()
        trigger = f"用户掉进「{title}」" if title else ""
        if not trigger or trigger in seen_feedback_triggers:
            continue
        feedback_routes.append(
            {
                "trigger": trigger,
                "diagnosis": truncate_text(item.get("why_wrong", "")),
                "next_step": truncate_text(item.get("correction", "")),
                "anchor_ids": list(normalize_anchor_ids(item.get("anchor_ids"))),
            }
        )
        seen_feedback_triggers.add(trigger)
        if len(feedback_routes) >= 3:
            break
    enriched["feedback_routes"] = feedback_routes

    search_hooks = list(enriched.get("search_hooks") or [])
    seen_queries = {
        str(item.get("query", "")).strip()
        for item in search_hooks
        if isinstance(item, dict)
    }

    def add_search_hook(query: str, reason: str) -> None:
        normalized_query = str(query).strip()
        if not normalized_query or normalized_query in seen_queries:
            return
        search_hooks.append({"query": normalized_query, "reason": reason})
        seen_queries.add(normalized_query)

    for atom in atoms:
        title = str(atom.get("canonical_title", "")).strip()
        if title:
            add_search_hook(f'"{title}"', "讲内核心知识原子")
            add_search_hook(f'"{course_name}" "{title}"', "课程名与知识原子联合检索")
        combined = " ".join(
            [
                str(atom.get("atom_type", "")).strip(),
                str(atom.get("summary", "")).strip(),
                str(atom.get("body_markdown", "")).strip(),
            ]
        )
        if title and any(
            keyword in combined
            for keyword in ("误区", "误导", "陷阱", "毒药", "反例", "易错", "错误")
        ):
            add_search_hook(f'"{title}" 易错点', "讲内误区/反例原子")
        if len(search_hooks) >= 6:
            break
    if len(search_hooks) < 6:
        for anchor in anchors:
            for item in anchor.get("formula_candidates") or []:
                if not isinstance(item, dict):
                    continue
                expression = (
                    str(item.get("normalized_expression", "")).strip()
                    or str(item.get("expression", "")).strip()
                )
                if expression:
                    add_search_hook(f'"{expression}"', "讲内公式候选")
                    add_search_hook(
                        f'"{course_name}" "{expression}"',
                        "课程名与公式候选联合检索",
                    )
                if len(search_hooks) >= 6:
                    break
            if len(search_hooks) >= 6:
                break
    add_search_hook(f'"{lecture_title}"', "讲次标题精确检索")
    add_search_hook(f'"{course_name}" "{lecture_title}"', "课程名与讲次名联合检索")
    enriched["search_hooks"] = search_hooks

    return enriched
