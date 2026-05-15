from __future__ import annotations

from typing import Any

from course2knowledge_lite_store import JsonCourseStore

GUIDE_MODES = {"continue", "walkthrough", "self_check", "recap"}

_MODE_ALIASES = {
    "continue_learning": "continue",
    "next": "continue",
    "next_lecture": "continue",
    "walk": "walkthrough",
    "guide": "walkthrough",
    "lecture": "walkthrough",
    "check": "self_check",
    "quiz": "self_check",
    "questions": "self_check",
    "review": "recap",
    "summary": "recap",
}


def get_learning_guide(
    *,
    store: JsonCourseStore,
    course_id: str,
    mode: str = "continue",
    lecture_id: str = "",
    lecture_sequence: int | str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Build a read-only guided-learning payload from public course evidence."""

    normalized_mode = _normalize_mode(mode)
    cleaned_course_id = str(course_id or "").strip()
    if not cleaned_course_id:
        raise ValueError("course_id is required")

    course = store.read_course(cleaned_course_id)
    lectures = _sorted_lectures(store.read_lectures(cleaned_course_id))
    if not lectures:
        return _blocked(
            course=course,
            course_id=cleaned_course_id,
            mode=normalized_mode,
            reason="no_lectures",
            message="No lectures are available in this course store.",
        )

    progress_by_lecture_id = _progress_by_lecture_id(store, cleaned_course_id)
    segments_by_lecture_id = {
        str(lecture.get("lecture_id") or ""): _sorted_segments(
            store.read_transcript_segments_if_exists(cleaned_course_id, str(lecture.get("lecture_id") or ""))
        )
        for lecture in lectures
    }
    selected_lecture = _select_lecture(
        lectures,
        progress_by_lecture_id=progress_by_lecture_id,
        segments_by_lecture_id=segments_by_lecture_id,
        lecture_id=lecture_id,
        lecture_sequence=lecture_sequence,
    )
    if selected_lecture is None:
        selector = f"lecture_id={lecture_id}" if lecture_id else f"lecture_sequence={lecture_sequence}"
        return _blocked(
            course=course,
            course_id=cleaned_course_id,
            mode=normalized_mode,
            reason="lecture_not_found",
            message=f"No lecture matched {selector}.",
        )

    evidence = _lecture_evidence(
        store=store,
        course_id=cleaned_course_id,
        lecture=selected_lecture,
        segments=segments_by_lecture_id.get(str(selected_lecture.get("lecture_id") or ""), []),
        limit=limit,
    )
    if normalized_mode in {"walkthrough", "self_check", "recap"} and not _has_any_evidence(evidence):
        return _blocked(
            course=course,
            course_id=cleaned_course_id,
            mode=normalized_mode,
            reason="no_guidance_evidence",
            message="No transcript, card, or visual evidence is available for the selected lecture.",
            lecture=selected_lecture,
            progress_summary=_progress_summary(lectures, progress_by_lecture_id, segments_by_lecture_id),
        )

    if normalized_mode == "continue":
        return _continue_payload(
            course=course,
            course_id=cleaned_course_id,
            lectures=lectures,
            selected_lecture=selected_lecture,
            progress_by_lecture_id=progress_by_lecture_id,
            segments_by_lecture_id=segments_by_lecture_id,
            evidence=evidence,
        )
    if normalized_mode == "walkthrough":
        return _walkthrough_payload(
            course=course,
            course_id=cleaned_course_id,
            selected_lecture=selected_lecture,
            progress_by_lecture_id=progress_by_lecture_id,
            segments_by_lecture_id=segments_by_lecture_id,
            evidence=evidence,
        )
    if normalized_mode == "self_check":
        return _self_check_payload(
            course=course,
            course_id=cleaned_course_id,
            selected_lecture=selected_lecture,
            progress_by_lecture_id=progress_by_lecture_id,
            segments_by_lecture_id=segments_by_lecture_id,
            evidence=evidence,
            limit=limit,
        )
    return _recap_payload(
        course=course,
        course_id=cleaned_course_id,
        lectures=lectures,
        selected_lecture=selected_lecture,
        progress_by_lecture_id=progress_by_lecture_id,
        segments_by_lecture_id=segments_by_lecture_id,
        evidence=evidence,
    )


def _continue_payload(
    *,
    course: dict[str, Any],
    course_id: str,
    lectures: list[dict[str, Any]],
    selected_lecture: dict[str, Any],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    status = _lecture_status(selected_lecture, progress_by_lecture_id)
    transcript_count = len(evidence["segments"])
    if transcript_count:
        reason = "This is the next non-read lecture with transcript evidence."
    else:
        reason = "This lecture is next in course order, but transcript evidence is not available yet."
    return _base_payload(
        course=course,
        course_id=course_id,
        mode="continue",
        lecture=selected_lecture,
        progress_summary=_progress_summary(lectures, progress_by_lecture_id, segments_by_lecture_id),
        extra={
            "recommendation": {
                "action": "continue_lecture",
                "reason": reason,
                "read_status": status,
                "has_transcript": transcript_count > 0,
            },
            "preview": {
                "segments": evidence["segment_citations"],
                "cards": evidence["cards"],
                "visual_evidence": evidence["visual_evidence"],
            },
        },
    )


def _walkthrough_payload(
    *,
    course: dict[str, Any],
    course_id: str,
    selected_lecture: dict[str, Any],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {
            "step_id": "orientation",
            "title": "Orient to the lecture",
            "body": f"Read the lecture '{_lecture_title(selected_lecture)}' and keep the cited evidence visible.",
            "citations": evidence["segment_citations"][:1],
        }
    ]
    for index, citation in enumerate(evidence["segment_citations"], start=1):
        steps.append(
            {
                "step_id": f"segment_{index}",
                "title": f"Evidence segment {index}",
                "body": _truncate(str(citation.get("text") or ""), 180),
                "citations": [citation],
            }
        )
    if evidence["cards"]:
        steps.append(
            {
                "step_id": "cards",
                "title": "Pin the knowledge cards",
                "body": "Use the linked cards as the compact concept map for this lecture.",
                "cards": evidence["cards"],
            }
        )
    if evidence["visual_evidence"]:
        steps.append(
            {
                "step_id": "visuals",
                "title": "Inspect visual evidence",
                "body": "Use the selected images only as course evidence, with their explanations attached.",
                "visual_evidence": evidence["visual_evidence"],
            }
        )
    return _base_payload(
        course=course,
        course_id=course_id,
        mode="walkthrough",
        lecture=selected_lecture,
        progress_summary=_progress_summary(
            [selected_lecture],
            progress_by_lecture_id,
            {str(selected_lecture.get("lecture_id") or ""): segments_by_lecture_id.get(str(selected_lecture.get("lecture_id") or ""), [])},
        ),
        extra={
            "walkthrough": steps,
            "evidence": evidence,
        },
    )


def _self_check_payload(
    *,
    course: dict[str, Any],
    course_id: str,
    selected_lecture: dict[str, Any],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    evidence: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    segment_by_id = {
        str(citation.get("segment_id") or ""): citation for citation in evidence["segment_citations"]
    }
    for card in evidence["cards"][: max(limit, 0)]:
        source_segment_ids = [str(item) for item in card.get("source_segment_ids") or []]
        citations = [segment_by_id[item] for item in source_segment_ids if item in segment_by_id]
        questions.append(
            {
                "question_id": f"self_check_{len(questions) + 1}",
                "prompt": f"Explain in your own words: {_truncate(str(card.get('title') or ''), 96)}",
                "source_card": card,
                "citations": citations,
                "answer_policy": "Use the cited course evidence; no automatic grading is performed.",
            }
        )
    for citation in evidence["segment_citations"]:
        if len(questions) >= max(limit, 0):
            break
        questions.append(
            {
                "question_id": f"self_check_{len(questions) + 1}",
                "prompt": f"What is the main idea of this segment: {_truncate(str(citation.get('text') or ''), 96)}",
                "source_card": {},
                "citations": [citation],
                "answer_policy": "Use the cited course evidence; no automatic grading is performed.",
            }
        )
    return _base_payload(
        course=course,
        course_id=course_id,
        mode="self_check",
        lecture=selected_lecture,
        progress_summary=_progress_summary(
            [selected_lecture],
            progress_by_lecture_id,
            {str(selected_lecture.get("lecture_id") or ""): segments_by_lecture_id.get(str(selected_lecture.get("lecture_id") or ""), [])},
        ),
        extra={
            "questions": questions,
            "question_count": len(questions),
            "grading": {
                "automatic_grading": False,
                "mastery_judgment": False,
                "answer_quality_score": False,
            },
        },
    )


def _recap_payload(
    *,
    course: dict[str, Any],
    course_id: str,
    lectures: list[dict[str, Any]],
    selected_lecture: dict[str, Any],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    key_points = [
        {
            "title": str(card.get("title") or ""),
            "body": _truncate(str(card.get("body") or ""), 180),
            "source_segment_ids": list(card.get("source_segment_ids") or []),
        }
        for card in evidence["cards"]
    ]
    if not key_points:
        key_points = [
            {
                "title": f"Segment {index}",
                "body": _truncate(str(citation.get("text") or ""), 180),
                "source_segment_ids": [str(citation.get("segment_id") or "")],
            }
            for index, citation in enumerate(evidence["segment_citations"], start=1)
        ]
    next_lecture = _next_non_read_after(lectures, selected_lecture, progress_by_lecture_id, segments_by_lecture_id)
    return _base_payload(
        course=course,
        course_id=course_id,
        mode="recap",
        lecture=selected_lecture,
        progress_summary=_progress_summary(lectures, progress_by_lecture_id, segments_by_lecture_id),
        extra={
            "recap": {
                "key_points": key_points,
                "visual_evidence": evidence["visual_evidence"],
                "next_reading_target": _lecture_public(next_lecture) if next_lecture else {},
                "next_options": [
                    "Read the cited segments again.",
                    "Ask a question against this course store.",
                    "Open the next transcript-backed lecture when ready.",
                ],
            }
        },
    )


def _base_payload(
    *,
    course: dict[str, Any],
    course_id: str,
    mode: str,
    lecture: dict[str, Any],
    progress_summary: dict[str, Any],
    extra: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "completed",
        "mode": mode,
        "course_id": course_id,
        "course": dict(course),
        "lecture": _lecture_public(lecture),
        "progress_summary": progress_summary,
        "limits": _limits(),
        **extra,
    }


def _blocked(
    *,
    course: dict[str, Any],
    course_id: str,
    mode: str,
    reason: str,
    message: str,
    lecture: dict[str, Any] | None = None,
    progress_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "blocked",
        "mode": mode,
        "course_id": course_id,
        "course": dict(course),
        "reason": reason,
        "message": message,
        "limits": _limits(),
    }
    if lecture is not None:
        payload["lecture"] = _lecture_public(lecture)
    if progress_summary is not None:
        payload["progress_summary"] = progress_summary
    return payload


def _limits() -> dict[str, Any]:
    return {
        "mode": "read_only_guided_learning",
        "external_llm_used": False,
        "writes_progress": False,
        "creates_study_plan": False,
        "creates_schedule": False,
        "scores_learner": False,
        "diagnoses_mastery": False,
        "spaced_review_queue": False,
        "exercise_feedback": False,
    }


def _normalize_mode(mode: str) -> str:
    cleaned = str(mode or "continue").strip().lower().replace("-", "_")
    normalized = _MODE_ALIASES.get(cleaned, cleaned)
    if normalized not in GUIDE_MODES:
        allowed = ", ".join(sorted(GUIDE_MODES))
        raise ValueError(f"mode must be one of: {allowed}")
    return normalized


def _sorted_lectures(lectures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(lecture) for lecture in lectures],
        key=lambda item: (int(item.get("sequence") or 0), str(item.get("lecture_id") or "")),
    )


def _sorted_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(segment) for segment in segments],
        key=lambda item: (float(item.get("start_seconds") or 0.0), str(item.get("segment_id") or "")),
    )


def _progress_by_lecture_id(store: JsonCourseStore, course_id: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("lecture_id") or ""): dict(item)
        for item in store.list_reading_progress(course_id=course_id)
        if str(item.get("lecture_id") or "")
    }


def _select_lecture(
    lectures: list[dict[str, Any]],
    *,
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    lecture_id: str = "",
    lecture_sequence: int | str | None = None,
) -> dict[str, Any] | None:
    cleaned_lecture_id = str(lecture_id or "").strip()
    if cleaned_lecture_id:
        return next((lecture for lecture in lectures if str(lecture.get("lecture_id") or "") == cleaned_lecture_id), None)
    if lecture_sequence not in (None, ""):
        try:
            parsed_sequence = int(lecture_sequence)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"lecture_sequence must be an integer: {lecture_sequence}") from exc
        return next((lecture for lecture in lectures if int(lecture.get("sequence") or 0) == parsed_sequence), None)
    for desired_status in ("reading", "not_started"):
        for lecture in lectures:
            lecture_key = str(lecture.get("lecture_id") or "")
            if _lecture_status(lecture, progress_by_lecture_id) == desired_status and segments_by_lecture_id.get(lecture_key):
                return lecture
    return next((lecture for lecture in lectures if segments_by_lecture_id.get(str(lecture.get("lecture_id") or ""))), lectures[0])


def _lecture_status(lecture: dict[str, Any], progress_by_lecture_id: dict[str, dict[str, Any]]) -> str:
    lecture_id = str(lecture.get("lecture_id") or "")
    progress = progress_by_lecture_id.get(lecture_id) or {}
    return str(progress.get("status") or lecture.get("read_status") or "not_started")


def _lecture_evidence(
    *,
    store: JsonCourseStore,
    course_id: str,
    lecture: dict[str, Any],
    segments: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    capped_limit = max(int(limit), 0)
    lecture_id = str(lecture.get("lecture_id") or "")
    cards = store.list_knowledge_cards(course_id=course_id, lecture_id=lecture_id)[:capped_limit]
    visuals = store.list_visual_evidence(course_id=course_id, lecture_id=lecture_id)[:capped_limit]
    selected_segments = segments[:capped_limit]
    return {
        "segments": selected_segments,
        "segment_citations": [_citation(course_id, lecture, segment) for segment in selected_segments],
        "cards": [dict(card) for card in cards],
        "visual_evidence": [dict(item) for item in visuals],
    }


def _has_any_evidence(evidence: dict[str, Any]) -> bool:
    return bool(evidence["segments"] or evidence["cards"] or evidence["visual_evidence"])


def _citation(course_id: str, lecture: dict[str, Any], segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_id": course_id,
        "lecture_id": str(lecture.get("lecture_id") or ""),
        "lecture_sequence": int(lecture.get("sequence") or 0),
        "lecture_title": _lecture_title(lecture),
        "segment_id": str(segment.get("segment_id") or ""),
        "start_seconds": float(segment.get("start_seconds") or 0.0),
        "end_seconds": float(segment.get("end_seconds") or 0.0),
        "text": str(segment.get("text") or ""),
    }


def _progress_summary(
    lectures: list[dict[str, Any]],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    counts = {"not_started": 0, "reading": 0, "read": 0}
    covered = 0
    for lecture in lectures:
        lecture_id = str(lecture.get("lecture_id") or "")
        status = _lecture_status(lecture, progress_by_lecture_id)
        counts[status] = counts.get(status, 0) + 1
        if segments_by_lecture_id.get(lecture_id):
            covered += 1
    total = len(lectures)
    return {
        "lecture_count": total,
        "transcript_covered_lecture_count": covered,
        "read_count": counts.get("read", 0),
        "reading_count": counts.get("reading", 0),
        "not_started_count": counts.get("not_started", 0),
        "coverage_ratio": round(covered / total, 4) if total else 0.0,
    }


def _next_non_read_after(
    lectures: list[dict[str, Any]],
    selected_lecture: dict[str, Any],
    progress_by_lecture_id: dict[str, dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    selected_sequence = int(selected_lecture.get("sequence") or 0)
    for lecture in lectures:
        if int(lecture.get("sequence") or 0) <= selected_sequence:
            continue
        lecture_id = str(lecture.get("lecture_id") or "")
        if _lecture_status(lecture, progress_by_lecture_id) != "read" and segments_by_lecture_id.get(lecture_id):
            return lecture
    return None


def _lecture_public(lecture: dict[str, Any] | None) -> dict[str, Any]:
    if lecture is None:
        return {}
    return {
        "lecture_id": str(lecture.get("lecture_id") or ""),
        "course_id": str(lecture.get("course_id") or ""),
        "title": _lecture_title(lecture),
        "sequence": int(lecture.get("sequence") or 0),
        "source_url": str(lecture.get("source_url") or ""),
        "source_id": str(lecture.get("source_id") or ""),
        "read_status": str(lecture.get("read_status") or "not_started"),
    }


def _lecture_title(lecture: dict[str, Any]) -> str:
    return str(lecture.get("title") or lecture.get("lecture_id") or "Untitled lecture")


def _truncate(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: max(limit - 3, 0)].rstrip()}..."
