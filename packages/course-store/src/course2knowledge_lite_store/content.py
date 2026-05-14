from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TranscriptCitation:
    course_id: str
    lecture_id: str
    lecture_sequence: int | None
    lecture_title: str
    segment_id: str
    start_seconds: float
    end_seconds: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "lecture_sequence": self.lecture_sequence,
            "lecture_title": self.lecture_title,
            "segment_id": self.segment_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }


def build_lecture_reader_payload(
    *,
    course: dict[str, Any],
    lecture: dict[str, Any],
    segments: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    normalized_segments = [_normalize_segment(segment) for segment in segments]
    return {
        "course": dict(course),
        "lecture": dict(lecture),
        "segments": normalized_segments,
        "segment_count": len(normalized_segments),
        "has_transcript": bool(normalized_segments),
    }


def search_transcript_segments(
    *,
    course_id: str,
    lectures: Iterable[dict[str, Any]],
    segments_by_lecture_id: dict[str, list[dict[str, Any]]],
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []
    results: list[dict[str, Any]] = []
    for lecture in sorted((dict(item) for item in lectures), key=lambda item: int(item.get("sequence") or 0)):
        lecture_id = str(lecture.get("lecture_id", "") or "")
        for segment in segments_by_lecture_id.get(lecture_id, []):
            citation = build_transcript_citation(course_id=course_id, lecture=lecture, segment=segment)
            score = _match_score(citation.text, terms)
            if score <= 0:
                continue
            results.append(
                {
                    "score": score,
                    "citation": citation.to_dict(),
                    "snippet": _snippet(citation.text, terms),
                }
            )
    results.sort(
        key=lambda item: (
            -int(item["score"]),
            int((item["citation"].get("lecture_sequence") or 0)),
            float(item["citation"].get("start_seconds") or 0.0),
        )
    )
    return results[: max(int(limit or 0), 0)]


def build_transcript_citation(
    *,
    course_id: str,
    lecture: dict[str, Any],
    segment: dict[str, Any],
) -> TranscriptCitation:
    normalized = _normalize_segment(segment)
    lecture_sequence = _optional_int(lecture.get("sequence"))
    return TranscriptCitation(
        course_id=course_id,
        lecture_id=str(lecture.get("lecture_id", "") or normalized.get("lecture_id", "")),
        lecture_sequence=lecture_sequence,
        lecture_title=str(lecture.get("title", "") or ""),
        segment_id=str(normalized.get("segment_id", "") or ""),
        start_seconds=float(normalized.get("start_seconds") or 0.0),
        end_seconds=float(normalized.get("end_seconds") or 0.0),
        text=str(normalized.get("text", "") or ""),
    )


def _normalize_segment(segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": str(segment.get("segment_id", "") or ""),
        "lecture_id": str(segment.get("lecture_id", "") or ""),
        "start_seconds": float(segment.get("start_seconds") or 0.0),
        "end_seconds": float(segment.get("end_seconds") or 0.0),
        "text": str(segment.get("text", "") or ""),
    }


def _query_terms(query: str) -> list[str]:
    return [term for term in str(query or "").lower().split() if term]


def _match_score(text: str, terms: list[str]) -> int:
    lowered = str(text or "").lower()
    return sum(lowered.count(term) for term in terms)


def _snippet(text: str, terms: list[str], radius: int = 42) -> str:
    if not terms:
        return str(text or "")
    lowered = str(text or "").lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return str(text or "")
    center = min(positions)
    start = max(center - radius, 0)
    end = min(center + radius, len(text))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

