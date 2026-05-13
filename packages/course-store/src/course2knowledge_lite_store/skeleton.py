from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from typing import Any, Iterable, Mapping

from .models import CourseRecord, CourseSkeleton, ImportStatusRecord, LectureRecord


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_course_id(source_url: str, title: str) -> str:
    digest = hashlib.sha1(f"{source_url}\n{title}".encode("utf-8")).hexdigest()[:12]
    return f"course_{digest}"


def _video_ref_value(video_ref: Any, field_name: str, default: Any = "") -> Any:
    if isinstance(video_ref, Mapping):
        return video_ref.get(field_name, default)
    return getattr(video_ref, field_name, default)


def _normalize_video_refs(video_refs: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_sequences: set[int] = set()
    seen_urls: set[str] = set()
    for index, video_ref in enumerate(video_refs, start=1):
        raw_sequence = _video_ref_value(video_ref, "sequence", index)
        try:
            sequence = int(raw_sequence)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid lecture sequence: {raw_sequence}") from exc
        if sequence <= 0:
            raise ValueError(f"Lecture sequence must be positive: {sequence}")
        bvid = str(_video_ref_value(video_ref, "bvid", "") or "").strip()
        title = str(_video_ref_value(video_ref, "title", "") or bvid or f"Lecture {sequence}").strip()
        source_url = str(_video_ref_value(video_ref, "source_url", "") or "").strip()
        if not source_url:
            raise ValueError(f"Lecture {sequence} is missing source_url")
        if sequence in seen_sequences:
            raise ValueError(f"Duplicate lecture sequence: {sequence}")
        if source_url in seen_urls:
            raise ValueError(f"Duplicate lecture source_url: {source_url}")
        seen_sequences.add(sequence)
        seen_urls.add(source_url)
        normalized.append(
            {
                "sequence": sequence,
                "bvid": bvid,
                "title": title,
                "source_url": source_url,
            }
        )
    normalized.sort(key=lambda item: int(item["sequence"]))
    if not normalized:
        raise ValueError("Course skeleton requires at least one lecture video ref")
    return normalized


def build_course_skeleton(
    *,
    title: str,
    source_url: str,
    video_refs: Iterable[Any],
    course_id: str | None = None,
    now: str | None = None,
) -> CourseSkeleton:
    cleaned_title = str(title or "").strip()
    cleaned_source_url = str(source_url or "").strip()
    if not cleaned_title:
        raise ValueError("Course title is required")
    if not cleaned_source_url:
        raise ValueError("Course source_url is required")
    timestamp = str(now or "").strip() or _utc_now_iso()
    resolved_course_id = str(course_id or "").strip() or _stable_course_id(cleaned_source_url, cleaned_title)
    normalized_video_refs = _normalize_video_refs(video_refs)
    course = CourseRecord(
        course_id=resolved_course_id,
        title=cleaned_title,
        source_url=cleaned_source_url,
        source_platform="bilibili",
        import_status="accepted",
        created_at=timestamp,
        updated_at=timestamp,
    )
    lectures = [
        LectureRecord(
            lecture_id=f"{resolved_course_id}::lecture::{item['sequence']:03d}",
            course_id=resolved_course_id,
            title=str(item["title"]),
            source_url=str(item["source_url"]),
            sequence=int(item["sequence"]),
            source_id=str(item["bvid"]),
            duration_seconds=None,
            read_status="not_started",
        )
        for item in normalized_video_refs
    ]
    import_status = ImportStatusRecord(
        import_id=f"import_{resolved_course_id}",
        course_id=resolved_course_id,
        source_url=cleaned_source_url,
        source_platform="bilibili",
        status="accepted",
        stage="collection_expanded",
        total_lectures=len(lectures),
        completed_lectures=0,
        failed_lectures=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    return CourseSkeleton(course=course, lectures=lectures, import_status=import_status)
