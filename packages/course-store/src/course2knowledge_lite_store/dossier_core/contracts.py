from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .adapters import ValidationError, format_timestamp_anchor


def _safe_confidence(raw: Any, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class EvidenceAnchor:
    anchor_id: str
    modality: str
    source_line_ids: tuple[int, ...]
    start_timestamp: str
    end_timestamp: str
    suggested_screenshot_timestamp: str
    evidence_quote: str
    frame_path: str | None = None
    ocr_text: str | None = None
    visual_summary: str | None = None
    needs_human_review: bool = False
    candidate_kind: str | None = None
    context_frame_count: int = 0
    formula_candidates: tuple[dict[str, Any], ...] = ()
    speaker_note: str | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class KnowledgeAtomCandidate:
    atom_id: str
    canonical_title: str
    atom_type: str
    summary: str
    body_markdown: str
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    anchor_ids: tuple[str, ...] = ()
    source_anchor_id: str = ""
    cross_references: tuple[str, ...] = ()
    review_questions: tuple[str, ...] = ()
    status: str = "locked"
    confidence: float = 0.0
    artifact_ref: str = ""


@dataclass(frozen=True)
class KnowledgeRelationCandidate:
    relation_id: str
    source_atom_id: str
    target_atom_id: str
    relation_type: str
    anchor_ids: tuple[str, ...] = ()
    evidence_quote: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class LectureDossierArtifact:
    course_name: str
    lecture_id: str
    lecture_slug: str
    artifact_root: Path
    subtitle_bundle_path: Path
    chunk_manifest_path: Path
    reduce_json_path: Path
    markdown_render_context_path: Path
    markdown_temp_path: Path


class LectureDossierPipelineError(RuntimeError):
    def __init__(self, message: str, *, partial_result: dict[str, str] | None = None):
        super().__init__(message)
        self.partial_result = partial_result or {}


_NUMBERED_STEP_PATTERN = re.compile(
    r"(?:^|(?<=[。；\n]))\s*(\d+[\.、]\s*.*?(?:[。；]|$))(?=(?:\s*\d+[\.、])|$)",
    flags=re.DOTALL,
)


def normalize_anchor_ids(raw_values: Any) -> tuple[str, ...]:
    return tuple(
        str(item).strip()
        for item in raw_values or []
        if str(item).strip()
    )


def normalize_tutoring_prerequisite(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    title = str(raw_item.get("title", "")).strip()
    if not title:
        return None
    return {
        "title": title,
        "why_it_matters": str(raw_item.get("why_it_matters", "")).strip(),
        "anchor_ids": list(normalize_anchor_ids(raw_item.get("anchor_ids"))),
    }


def normalize_tutoring_pitfall(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    title = str(raw_item.get("title", "")).strip()
    if not title:
        return None
    return {
        "title": title,
        "why_wrong": str(raw_item.get("why_wrong", "")).strip(),
        "correction": str(raw_item.get("correction", "")).strip(),
        "anchor_ids": list(normalize_anchor_ids(raw_item.get("anchor_ids"))),
    }


def normalize_tutoring_example(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    title = str(raw_item.get("title", "")).strip()
    if not title:
        return None
    raw_steps = raw_item.get("steps") or []
    steps: list[str] = []
    if isinstance(raw_steps, str):
        normalized_steps = raw_steps.strip()
        if normalized_steps:
            numbered_matches = [
                re.sub(r"^\d+[\.、]\s*", "", match.strip()).strip()
                for match in _NUMBERED_STEP_PATTERN.findall(normalized_steps)
            ]
            cleaned_matches = [item for item in numbered_matches if item]
            if cleaned_matches:
                steps = cleaned_matches
            else:
                steps = [line.strip() for line in normalized_steps.splitlines() if line.strip()]
                if not steps:
                    steps = [normalized_steps]
    else:
        steps = [
            str(item).strip()
            for item in raw_steps
            if str(item).strip()
        ]
    return {
        "title": title,
        "problem": str(raw_item.get("problem", "")).strip(),
        "steps": steps,
        "takeaway": str(raw_item.get("takeaway", "")).strip(),
        "anchor_ids": list(normalize_anchor_ids(raw_item.get("anchor_ids"))),
    }


def normalize_followup_scaffold(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    target = str(raw_item.get("target", "")).strip()
    if not target:
        return None
    return {
        "target": target,
        "probe_focus": str(raw_item.get("probe_focus", "")).strip(),
        "escalation_rule": str(raw_item.get("escalation_rule", "")).strip(),
        "anchor_ids": list(normalize_anchor_ids(raw_item.get("anchor_ids"))),
    }


def normalize_feedback_route(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    trigger = str(raw_item.get("trigger", "")).strip()
    if not trigger:
        return None
    return {
        "trigger": trigger,
        "diagnosis": str(raw_item.get("diagnosis", "")).strip(),
        "next_step": str(raw_item.get("next_step", "")).strip(),
        "anchor_ids": list(normalize_anchor_ids(raw_item.get("anchor_ids"))),
    }


def normalize_search_hook(raw_item: Any) -> dict[str, Any] | None:
    if not isinstance(raw_item, dict):
        return None
    query = str(raw_item.get("query", "")).strip()
    if not query:
        return None
    return {
        "query": query,
        "reason": str(raw_item.get("reason", "")).strip(),
    }


def serialize_anchor(anchor: EvidenceAnchor) -> dict[str, Any]:
    return {
        "anchor_id": anchor.anchor_id,
        "modality": anchor.modality,
        "source_line_ids": list(anchor.source_line_ids),
        "start_timestamp": anchor.start_timestamp,
        "end_timestamp": anchor.end_timestamp,
        "suggested_screenshot_timestamp": anchor.suggested_screenshot_timestamp,
        "evidence_quote": anchor.evidence_quote,
        "frame_path": anchor.frame_path,
        "ocr_text": anchor.ocr_text,
        "visual_summary": anchor.visual_summary,
        "needs_human_review": anchor.needs_human_review,
        "candidate_kind": anchor.candidate_kind,
        "context_frame_count": anchor.context_frame_count,
        "formula_candidates": [dict(item) for item in anchor.formula_candidates],
        "speaker_note": anchor.speaker_note,
        "confidence": anchor.confidence,
    }


def serialize_atom(atom: KnowledgeAtomCandidate) -> dict[str, Any]:
    return {
        "atom_id": atom.atom_id,
        "canonical_title": atom.canonical_title,
        "atom_type": atom.atom_type,
        "summary": atom.summary,
        "body_markdown": atom.body_markdown,
        "aliases": list(atom.aliases),
        "tags": list(atom.tags),
        "anchor_ids": list(atom.anchor_ids),
        "source_anchor_id": atom.source_anchor_id,
        "cross_references": list(atom.cross_references),
        "review_questions": list(atom.review_questions),
        "status": atom.status,
        "confidence": atom.confidence,
        "artifact_ref": atom.artifact_ref,
    }


def serialize_relation(relation: KnowledgeRelationCandidate) -> dict[str, Any]:
    return {
        "relation_id": relation.relation_id,
        "source_atom_id": relation.source_atom_id,
        "target_atom_id": relation.target_atom_id,
        "relation_type": relation.relation_type,
        "anchor_ids": list(relation.anchor_ids),
        "evidence_quote": relation.evidence_quote,
        "confidence": relation.confidence,
    }


def normalize_anchor(
    raw_anchor: dict[str, Any],
    *,
    default_anchor_id: str,
    default_source_line_ids: tuple[int, ...] = (),
    default_start_timestamp: str = "",
    default_end_timestamp: str = "",
    default_suggested_timestamp: str = "",
) -> EvidenceAnchor:
    evidence_quote = str(raw_anchor.get("evidence_quote", "")).strip()
    if not evidence_quote:
        raise ValidationError(["Lecture dossier anchor requires evidence_quote"])
    salvage_applied = False
    raw_line_ids = raw_anchor.get("source_line_ids") or []
    normalized_line_ids: list[int] = []
    for item in raw_line_ids:
        try:
            line_id = int(item)
        except (TypeError, ValueError):
            continue
        if line_id > 0:
            normalized_line_ids.append(line_id)
    source_line_ids = tuple(normalized_line_ids)
    if not source_line_ids:
        if default_source_line_ids:
            source_line_ids = tuple(int(item) for item in default_source_line_ids if int(item) > 0)
            salvage_applied = bool(source_line_ids)
        if not source_line_ids:
            raise ValidationError(["Lecture dossier anchor requires source_line_ids"])
    start_timestamp = str(raw_anchor.get("start_timestamp", "")).strip() or str(default_start_timestamp or "").strip()
    end_timestamp = str(raw_anchor.get("end_timestamp", "")).strip() or str(default_end_timestamp or "").strip()
    suggested_timestamp = str(
        raw_anchor.get(
            "suggested_screenshot_timestamp",
            str(default_suggested_timestamp or default_start_timestamp or start_timestamp),
        )
    ).strip()
    if str(raw_anchor.get("start_timestamp", "")).strip() == "":
        salvage_applied = True
    if str(raw_anchor.get("end_timestamp", "")).strip() == "":
        salvage_applied = True
    if str(raw_anchor.get("suggested_screenshot_timestamp", "")).strip() == "":
        salvage_applied = True
    if not start_timestamp or not end_timestamp:
        raise ValidationError(
            ["Lecture dossier anchor requires start_timestamp and end_timestamp"]
        )
    return EvidenceAnchor(
        anchor_id=str(raw_anchor.get("anchor_id", "")).strip() or default_anchor_id,
        modality=str(raw_anchor.get("modality", "subtitle")).strip() or "subtitle",
        source_line_ids=source_line_ids,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        suggested_screenshot_timestamp=suggested_timestamp,
        evidence_quote=evidence_quote,
        frame_path=(str(raw_anchor.get("frame_path", "")).strip() or None),
        ocr_text=(str(raw_anchor.get("ocr_text", "")).strip() or None),
        visual_summary=(str(raw_anchor.get("visual_summary", "")).strip() or None),
        needs_human_review=bool(raw_anchor.get("needs_human_review", False) or salvage_applied),
        candidate_kind=(
            str(raw_anchor.get("candidate_kind", "")).strip()
            or ("schema_salvaged_anchor" if salvage_applied else None)
        ),
        context_frame_count=int(raw_anchor.get("context_frame_count", 0) or 0),
        formula_candidates=tuple(
            dict(item)
            for item in raw_anchor.get("formula_candidates") or []
            if isinstance(item, dict)
        ),
        speaker_note=(str(raw_anchor.get("speaker_note", "")).strip() or None),
        confidence=_safe_confidence(raw_anchor.get("confidence", 0.0)),
    )


def normalize_atom(
    raw_atom: dict[str, Any], *, artifact_ref: str
) -> KnowledgeAtomCandidate:
    canonical_title = str(raw_atom.get("canonical_title", "")).strip()
    if not canonical_title:
        raise ValidationError(["Lecture dossier atom requires canonical_title"])
    atom_id = str(raw_atom.get("atom_id", "")).strip() or canonical_title
    return KnowledgeAtomCandidate(
        atom_id=atom_id,
        canonical_title=canonical_title,
        atom_type=str(raw_atom.get("atom_type", "concept")).strip() or "concept",
        summary=str(raw_atom.get("summary", "")).strip(),
        body_markdown=str(raw_atom.get("body_markdown", "")).strip(),
        aliases=tuple(
            str(item).strip()
            for item in raw_atom.get("aliases") or []
            if str(item).strip()
        ),
        tags=tuple(
            str(item).strip()
            for item in raw_atom.get("tags") or []
            if str(item).strip()
        ),
        anchor_ids=tuple(
            str(item).strip()
            for item in raw_atom.get("anchor_ids") or []
            if str(item).strip()
        ),
        source_anchor_id=str(raw_atom.get("source_anchor_id", "")).strip(),
        cross_references=tuple(
            str(item).strip()
            for item in raw_atom.get("cross_references") or []
            if str(item).strip()
        ),
        review_questions=tuple(
            str(item).strip()
            for item in raw_atom.get("review_questions") or []
            if str(item).strip()
        ),
        status=str(raw_atom.get("status", "locked")).strip() or "locked",
        confidence=_safe_confidence(raw_atom.get("confidence", 0.0)),
        artifact_ref=artifact_ref,
    )


def normalize_relation(raw_relation: dict[str, Any]) -> KnowledgeRelationCandidate:
    relation_id = str(raw_relation.get("relation_id", "")).strip()
    source_atom_id = str(raw_relation.get("source_atom_id", "")).strip()
    target_atom_id = str(raw_relation.get("target_atom_id", "")).strip()
    relation_type = str(raw_relation.get("relation_type", "")).strip()
    if not source_atom_id or not target_atom_id or not relation_type:
        raise ValidationError(
            [
                "Lecture dossier relation requires source_atom_id, target_atom_id, and relation_type"
            ]
        )
    return KnowledgeRelationCandidate(
        relation_id=relation_id
        or f"{source_atom_id}->{target_atom_id}:{relation_type}",
        source_atom_id=source_atom_id,
        target_atom_id=target_atom_id,
        relation_type=relation_type,
        anchor_ids=tuple(
            str(item).strip()
            for item in raw_relation.get("anchor_ids") or []
            if str(item).strip()
        ),
        evidence_quote=str(raw_relation.get("evidence_quote", "")).strip(),
        confidence=_safe_confidence(raw_relation.get("confidence", 0.0)),
    )


def build_anchor_from_line_span(
    *,
    anchor_id: str,
    source_line_ids: list[int],
    timed_lines: list[dict[str, Any]],
    evidence_quote: str,
    confidence: float = 0.0,
) -> EvidenceAnchor:
    if not source_line_ids:
        raise ValidationError(["Cannot build anchor without source_line_ids"])
    first_line = timed_lines[source_line_ids[0] - 1]
    last_line = timed_lines[source_line_ids[-1] - 1]
    start_timestamp = format_timestamp_anchor(first_line.get("start_seconds", 0.0))
    end_timestamp = format_timestamp_anchor(last_line.get("end_seconds", 0.0))
    return EvidenceAnchor(
        anchor_id=anchor_id,
        modality="subtitle",
        source_line_ids=tuple(source_line_ids),
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        suggested_screenshot_timestamp=start_timestamp,
        evidence_quote=evidence_quote,
        confidence=confidence,
    )
