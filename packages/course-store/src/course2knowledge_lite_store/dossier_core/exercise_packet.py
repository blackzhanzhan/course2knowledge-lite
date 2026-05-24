from __future__ import annotations

from hashlib import sha1
import re
from pathlib import Path
from typing import Any


_URL_RE = re.compile(r"https?://[^\s)\]]+", flags=re.IGNORECASE)
_SECRET_QUERY_RE = re.compile(
    r"(?i)(sekey|token|access_token|api_key|apikey|signature|sign|pwd|randsk)=([^&\s)]+)"
)
_SENSITIVE_KEY_PARTS = (
    "sekey",
    "cookie",
    "playlist",
    "signed",
    "signature",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "randsk",
)
_VISUAL_TEXT_KEYS = (
    "question_stem",
    "visual_question_text",
    "ocr_text",
    "screen_text",
    "visual_text",
    "text",
)
_ASK_MARKERS = ("?", "?", "求", "多少", "几", "how many", "what")
_EXERCISE_MARKERS = (
    "exercise",
    "question",
    "problem",
    "recap",
    "practice",
    "how many",
    "\u9898",
    "\u590d\u76d8",
    "\u4f8b\u9898",
    "\u7ec3\u4e60",
    "\u68f0",
)


def derive_exercise_teaching_packet(
    *,
    dossier: dict[str, Any],
    timed_lines: list[dict[str, Any]] | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a derived question-level teaching packet from dossier evidence."""

    anchors = [item for item in dossier.get("anchors") or [] if isinstance(item, dict)]
    visual_anchors = [item for item in anchors if _anchor_has_visual_evidence(item)]
    visual_text_sources = _collect_visual_text_sources(visual_anchors)
    question_stem = _select_question_stem(visual_text_sources)
    conditions, ask = _split_question_parts(question_stem)
    evidence_quotes = _collect_subtitle_evidence(visual_anchors, timed_lines)
    reasoning_text = "\n".join(_iter_reasoning_text(dossier))
    is_candidate = _looks_like_exercise_candidate(
        dossier=dossier,
        question_stem=question_stem,
        reasoning_text=reasoning_text,
    )
    conflicts = (
        _detect_reasoning_conflicts(
            reasoning_text=reasoning_text,
            question_stem=question_stem,
        )
        if is_candidate
        else []
    )
    review_blockers: list[dict[str, str]] = []
    if is_candidate and visual_anchors and not question_stem:
        review_blockers.append(
            {
                "code": "visual_text_missing",
                "message": "Visual frame exists, but no OCR/question text is available for the packet.",
            }
        )
    if is_candidate and not visual_anchors:
        review_blockers.append(
            {
                "code": "visual_anchor_missing",
                "message": "No visual anchor frame is available for question-level teaching.",
            }
        )

    if not is_candidate:
        status = "not_applicable"
    elif conflicts:
        status = "blocked_conflict"
    elif review_blockers:
        status = "review_required"
    else:
        status = "ready"

    packet_id_seed = "|".join(
        [
            str(dossier.get("course_name", "")),
            str(dossier.get("lecture_id", "")),
            str(dossier.get("lecture_title", "")),
            question_stem[:256],
        ]
    )
    safe_artifact_ref = (
        str(Path(artifact_root).resolve())
        if artifact_root
        else _safe_text(dossier.get("artifact_ref", ""))
    )
    return {
        "schema_version": "exercise_teaching_packet.v1",
        "packet_id": "exercise_"
        + sha1(packet_id_seed.encode("utf-8", errors="ignore")).hexdigest()[:12],
        "status": status,
        "teaching_allowed": status == "ready",
        "course_name": _safe_text(dossier.get("course_name", "")),
        "lecture_id": _safe_text(dossier.get("lecture_id", "")),
        "lecture_title": _safe_text(dossier.get("lecture_title", "")),
        "artifact_ref": safe_artifact_ref,
        "question_stem": question_stem,
        "conditions": conditions,
        "ask": ask,
        "solving_entry": _build_solving_entry(
            dossier=dossier,
            status=status,
            question_stem=question_stem,
        ),
        "step_skeleton": _build_step_skeleton(dossier),
        "trap": _build_trap(dossier),
        "student_answer_slot": _build_student_answer_slot(status=status, ask=ask),
        "variant_check": _build_variant_check(dossier),
        "evidence": {
            "visual_anchors": [_safe_anchor_ref(item) for item in visual_anchors],
            "subtitle_quotes": evidence_quotes,
            "visual_text_sources": visual_text_sources,
        },
        "conflicts": conflicts,
        "review_blockers": review_blockers,
        "boundary": {
            "kind": "derived_import_payload",
            "not_a_feishu_entity": True,
            "no_schema_change_required": True,
        },
    }


def _anchor_has_visual_evidence(anchor: dict[str, Any]) -> bool:
    return bool(
        _safe_local_path(anchor.get("frame_path"))
        or _safe_text(anchor.get("ocr_text", ""))
        or anchor.get("formula_candidates")
    )


def _looks_like_exercise_candidate(
    *,
    dossier: dict[str, Any],
    question_stem: str,
    reasoning_text: str,
) -> bool:
    haystack = " ".join(
        [
            _safe_text(dossier.get("lecture_title", "")),
            _safe_text(dossier.get("lecture_slug", "")),
            question_stem,
            reasoning_text[:2000],
        ]
    ).lower()
    return any(marker.lower() in haystack for marker in _EXERCISE_MARKERS)


def _collect_visual_text_sources(visual_anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for anchor in visual_anchors:
        anchor_id = _safe_text(anchor.get("anchor_id", ""))
        for key in _VISUAL_TEXT_KEYS:
            value = _safe_text(anchor.get(key, ""))
            if value:
                sources.append({"anchor_id": anchor_id, "field": key, "text": value})
        formula_text = _formula_candidates_to_text(anchor.get("formula_candidates") or [])
        if formula_text:
            sources.append(
                {
                    "anchor_id": anchor_id,
                    "field": "formula_candidates",
                    "text": formula_text,
                }
            )
    sources.sort(key=lambda item: len(str(item.get("text", ""))), reverse=True)
    return sources[:5]


def _formula_candidates_to_text(raw_items: Any) -> str:
    parts: list[str] = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        for key in ("text", "formula", "latex", "normalized", "expression"):
            value = _safe_text(item.get(key, ""))
            if value:
                parts.append(value)
                break
    return "\n".join(parts)


def _select_question_stem(visual_text_sources: list[dict[str, Any]]) -> str:
    for item in visual_text_sources:
        field = str(item.get("field", "")).strip()
        text = _safe_text(item.get("text", ""))
        if text and field != "formula_candidates":
            return text
    return ""


def _split_question_parts(question_stem: str) -> tuple[list[str], str]:
    if not question_stem:
        return [], ""
    segments = [
        segment.strip()
        for segment in re.split(r"[\n;；。]+|(?<!\d)\.(?!\d)", question_stem)
        if segment.strip()
    ]
    ask = ""
    conditions: list[str] = []
    for segment in segments:
        lowered = segment.lower()
        if not ask and any(marker in lowered for marker in _ASK_MARKERS):
            ask = segment
            continue
        conditions.append(segment)
    if not ask and segments:
        ask = segments[-1]
        conditions = segments[:-1]
    return conditions[:12], ask


def _collect_subtitle_evidence(
    visual_anchors: list[dict[str, Any]],
    timed_lines: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []
    for anchor in visual_anchors:
        quote = _safe_text(anchor.get("evidence_quote", ""))
        if quote:
            quotes.append(
                {
                    "anchor_id": _safe_text(anchor.get("anchor_id", "")),
                    "start_timestamp": _safe_text(anchor.get("start_timestamp", "")),
                    "end_timestamp": _safe_text(anchor.get("end_timestamp", "")),
                    "quote": quote,
                }
            )
    if not quotes:
        for index, line in enumerate(timed_lines or [], start=1):
            quote = _safe_text(line.get("text", ""))
            if quote:
                quotes.append(
                    {
                        "anchor_id": f"subtitle_line_{index}",
                        "start_timestamp": _safe_text(line.get("start_timestamp", "")),
                        "end_timestamp": _safe_text(line.get("end_timestamp", "")),
                        "quote": quote,
                    }
                )
            if len(quotes) >= 3:
                break
    return quotes[:5]


def _iter_reasoning_text(dossier: dict[str, Any]):
    for key in ("lecture_title", "lecture_summary"):
        value = _safe_text(dossier.get(key, ""))
        if value:
            yield value
    for item in dossier.get("sections") or []:
        if isinstance(item, dict):
            yield _safe_text(item.get("heading", ""))
            yield _safe_text(item.get("body", ""))
    for item in dossier.get("atoms") or []:
        if isinstance(item, dict):
            yield _safe_text(item.get("canonical_title", ""))
            yield _safe_text(item.get("summary", ""))
            yield _safe_text(item.get("body_markdown", ""))
    for item in dossier.get("pitfalls") or []:
        if isinstance(item, dict):
            yield _safe_text(item.get("title", ""))
            yield _safe_text(item.get("why_wrong", ""))
            yield _safe_text(item.get("correction", ""))
    for item in dossier.get("relations") or []:
        if isinstance(item, dict):
            yield _safe_text(item.get("relation_type", ""))
            yield _safe_text(item.get("evidence_quote", ""))


def _detect_reasoning_conflicts(
    *,
    reasoning_text: str,
    question_stem: str,
) -> list[dict[str, Any]]:
    observations = _extract_xn_observations(reasoning_text)
    distinct_values = sorted({item["rounded_value"] for item in observations})
    conflicts: list[dict[str, Any]] = []
    if len(distinct_values) > 1:
        conflicts.append(
            {
                "type": "inconsistent_xn_values",
                "status": "blocks_confirmed_teaching",
                "values": distinct_values,
                "evidence": observations[:8],
            }
        )
    lowered_stem = question_stem.lower()
    if ("double" in lowered_stem or "twice" in lowered_stem or "2n" in lowered_stem) and any(
        item.get("n_factor") == 1.0 and item.get("coefficient") in {0.6, 0.60}
        for item in observations
    ):
        conflicts.append(
            {
                "type": "visual_quantity_factor_mismatch",
                "status": "blocks_confirmed_teaching",
                "message": "Visual stem indicates doubled output, while compiled reasoning also contains an n-only 0.6x*n equation.",
            }
        )
    return conflicts


def _extract_xn_observations(text: str) -> list[dict[str, Any]]:
    normalized = _normalize_math_text(text)
    observations: list[dict[str, Any]] = []
    equation_re = re.compile(
        r"(?P<coef>\d+(?:\.\d+)?)?\*?x(?:\*(?P<nfactor>\d+(?:\.\d+)?))?\*?n=(?P<rhs>\d+(?:\.\d+)?)"
    )
    for match in equation_re.finditer(normalized):
        coef = _safe_float(match.group("coef"), default=1.0)
        n_factor = _safe_float(match.group("nfactor"), default=1.0)
        rhs = _safe_float(match.group("rhs"), default=0.0)
        if coef == 0 or n_factor == 0:
            continue
        implied = rhs / coef / n_factor
        observations.append(
            {
                "kind": "equation",
                "expression": match.group(0),
                "coefficient": round(coef, 6),
                "n_factor": round(n_factor, 6),
                "rhs": round(rhs, 6),
                "implied_xn": round(implied, 6),
                "rounded_value": _round_value(implied),
            }
        )
    direct_re = re.compile(r"(?<![0-9.*])x\*?n=(?P<value>\d+(?:\.\d+)?)")
    for match in direct_re.finditer(normalized):
        value = _safe_float(match.group("value"), default=0.0)
        observations.append(
            {
                "kind": "direct",
                "expression": match.group(0),
                "implied_xn": round(value, 6),
                "rounded_value": _round_value(value),
            }
        )
    return observations


def _normalize_math_text(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.replace("x", "x")
    normalized = normalized.replace("×", "*").replace("脳", "*").replace("乘", "*")
    normalized = normalized.replace("＝", "=").replace(" ", "")
    normalized = re.sub(r"[\n\r\t]+", "", normalized)
    return normalized


def _round_value(value: float) -> str:
    rounded = round(value, 6)
    if abs(rounded - int(rounded)) < 0.000001:
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _safe_float(raw: Any, *, default: float) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _build_solving_entry(*, dossier: dict[str, Any], status: str, question_stem: str) -> str:
    if status == "blocked_conflict":
        return "Stop before teaching: reconcile the visual stem with compiled equations first."
    if not question_stem:
        return "Start from the screenshot/OCR stem after human review; compiled notes are secondary."
    for item in dossier.get("sections") or []:
        if isinstance(item, dict):
            body = _safe_text(item.get("body", ""))
            if body:
                return body[:320]
    return "Read the stem, bind variables, write the equation, then compute the answer."


def _build_step_skeleton(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[str] = []
    for atom in dossier.get("atoms") or []:
        if not isinstance(atom, dict):
            continue
        atom_type = _safe_text(atom.get("atom_type", "")).lower()
        body = _safe_text(atom.get("body_markdown", ""))
        title = _safe_text(atom.get("canonical_title", ""))
        if "procedure" in atom_type or "step" in title.lower():
            steps.extend(_split_steps(body))
    if not steps:
        for example in dossier.get("minimal_examples") or []:
            if isinstance(example, dict):
                steps.extend(_safe_text(item) for item in example.get("steps") or [])
    if not steps:
        steps = [
            "Identify variables from the visual stem.",
            "Translate every condition into one equation.",
            "Compute the target quantity and check units.",
        ]
    return [
        {
            "index": index,
            "action": step[:360],
        }
        for index, step in enumerate([item for item in steps if item], start=1)
    ][:8]


def _split_steps(text: str) -> list[str]:
    raw = _safe_text(text)
    if not raw:
        return []
    numbered = re.split(r"(?:^|[;；。]\s*)\d+[.、]\s*", raw)
    steps = [item.strip(" ;；。") for item in numbered if item.strip(" ;；。")]
    if len(steps) > 1:
        return steps
    return [item.strip() for item in raw.splitlines() if item.strip()]


def _build_trap(dossier: dict[str, Any]) -> dict[str, Any]:
    for item in dossier.get("pitfalls") or []:
        if isinstance(item, dict):
            title = _safe_text(item.get("title", ""))
            why_wrong = _safe_text(item.get("why_wrong", ""))
            correction = _safe_text(item.get("correction", ""))
            if title or why_wrong or correction:
                return {
                    "title": title,
                    "why_wrong": why_wrong,
                    "correction": correction,
                }
    return {
        "title": "Equation-source drift",
        "why_wrong": "Solving from compiled notes before reading the visual stem can hide condition errors.",
        "correction": "Return to the question stem, then rebuild the equation step by step.",
    }


def _build_student_answer_slot(*, status: str, ask: str) -> dict[str, Any]:
    return {
        "type": "free_text",
        "prompt": ask or "Write the equation setup and final answer.",
        "requires_equation": True,
        "locked_until_review": status != "ready",
    }


def _build_variant_check(dossier: dict[str, Any]) -> dict[str, Any]:
    questions = [
        _safe_text(item)
        for item in dossier.get("review_questions") or []
        if _safe_text(item)
    ]
    if questions:
        return {
            "prompt": questions[0],
            "purpose": "Check whether the student can transfer the setup, not only repeat the answer.",
        }
    for example in dossier.get("minimal_examples") or []:
        if isinstance(example, dict):
            problem = _safe_text(example.get("problem", ""))
            if problem:
                return {
                    "prompt": problem,
                    "purpose": "Variant transfer check.",
                }
    return {
        "prompt": "Change one condition and ask whether the same equation still holds.",
        "purpose": "Guard against memorized arithmetic.",
    }


def _safe_anchor_ref(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor_id": _safe_text(anchor.get("anchor_id", "")),
        "start_timestamp": _safe_text(anchor.get("start_timestamp", "")),
        "end_timestamp": _safe_text(anchor.get("end_timestamp", "")),
        "suggested_screenshot_timestamp": _safe_text(
            anchor.get("suggested_screenshot_timestamp", "")
        ),
        "evidence_quote": _safe_text(anchor.get("evidence_quote", "")),
        "frame_path": _safe_local_path(anchor.get("frame_path")),
        "has_ocr_text": bool(_safe_text(anchor.get("ocr_text", ""))),
    }


def _safe_local_path(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "://" in lowered or "?" in text:
        return ""
    if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
        return ""
    return text


def _safe_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = _SECRET_QUERY_RE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return _URL_RE.sub("[redacted-url]", text)
