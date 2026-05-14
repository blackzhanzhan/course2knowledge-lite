from __future__ import annotations

from pathlib import Path
from typing import Any

from course2knowledge_lite_store import JsonCourseStore, build_course_skeleton, build_transcript_segments

from .collection import JsonFetcher, expand_bilibili_collection_url
from .subtitles import fetch_bilibili_timed_subtitles


def import_collection_skeleton_to_store(
    source_url: str,
    *,
    store_root: str | Path,
    now: str | None = None,
    fetch_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    collection = expand_bilibili_collection_url(source_url, fetch_json=fetch_json)
    skeleton = build_course_skeleton(
        title=collection.title,
        source_url=collection.source_url,
        video_refs=collection.videos,
        now=now,
    )
    paths = JsonCourseStore(store_root).write_skeleton(skeleton)
    return {
        "course": skeleton.course.to_dict(),
        "lectures": [lecture.to_dict() for lecture in skeleton.lectures],
        "import_status": skeleton.import_status.to_dict(),
        "paths": paths,
    }


def import_lecture_transcript_to_store(
    *,
    store_root: str | Path,
    course_id: str,
    lecture: dict[str, Any],
    fetch_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    lecture_id = str(lecture.get("lecture_id", "") or "").strip()
    source_url = str(lecture.get("source_url", "") or "").strip()
    if not lecture_id:
        raise ValueError("lecture.lecture_id is required")
    if not source_url:
        raise ValueError("lecture.source_url is required")
    subtitles = fetch_bilibili_timed_subtitles(source_url, fetch_json=fetch_json)
    segments = build_transcript_segments(lecture=lecture, timed_lines=subtitles.timed_lines)
    path = JsonCourseStore(store_root).write_transcript_segments(course_id, lecture_id, segments)
    return {
        "lecture_id": lecture_id,
        "source_id": subtitles.source_id,
        "segment_count": len(segments),
        "path": path,
    }


def import_lecture_transcript_by_reference_to_store(
    *,
    store_root: str | Path,
    course_id: str = "",
    import_id: str = "",
    lecture_sequence: int | str | None = None,
    lecture_id: str = "",
    source_id: str = "",
    fetch_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    store = JsonCourseStore(store_root)
    resolved_course_id = str(course_id or "").strip()
    resolved_import_status: dict[str, Any] | None = None

    cleaned_import_id = str(import_id or "").strip()
    if cleaned_import_id:
        resolved_import_status = store.read_import_status(cleaned_import_id)
        import_course_id = str(resolved_import_status.get("course_id", "") or "").strip()
        if not import_course_id:
            raise ValueError(f"Import status {cleaned_import_id} does not expose a course_id")
        if resolved_course_id and resolved_course_id != import_course_id:
            raise ValueError(
                f"course_id {resolved_course_id} does not match import {cleaned_import_id} course_id {import_course_id}"
            )
        resolved_course_id = import_course_id

    if not resolved_course_id:
        raise ValueError("course_id or import_id is required")

    lecture = _select_lecture(
        store.read_lectures(resolved_course_id),
        lecture_sequence=lecture_sequence,
        lecture_id=lecture_id,
        source_id=source_id,
    )
    result = import_lecture_transcript_to_store(
        store_root=store_root,
        course_id=resolved_course_id,
        lecture=lecture,
        fetch_json=fetch_json,
    )
    return {
        **result,
        "course_id": resolved_course_id,
        "import_id": cleaned_import_id,
        "lecture": lecture,
        "import_status": resolved_import_status,
    }


def _select_lecture(
    lectures: list[dict[str, Any]],
    *,
    lecture_sequence: int | str | None = None,
    lecture_id: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    cleaned_lecture_id = str(lecture_id or "").strip()
    cleaned_source_id = str(source_id or "").strip()
    parsed_sequence: int | None = None
    if lecture_sequence not in (None, ""):
        try:
            parsed_sequence = int(lecture_sequence)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"lecture_sequence must be an integer: {lecture_sequence}") from exc
        if parsed_sequence <= 0:
            raise ValueError(f"lecture_sequence must be positive: {parsed_sequence}")

    if not any((cleaned_lecture_id, cleaned_source_id, parsed_sequence is not None)):
        raise ValueError("lecture_sequence, lecture_id, or source_id is required")

    for lecture in lectures:
        if cleaned_lecture_id and str(lecture.get("lecture_id", "") or "").strip() == cleaned_lecture_id:
            return dict(lecture)
        if cleaned_source_id and str(lecture.get("source_id", "") or "").strip() == cleaned_source_id:
            return dict(lecture)
        if parsed_sequence is not None:
            try:
                sequence = int(lecture.get("sequence", 0) or 0)
            except (TypeError, ValueError):
                sequence = 0
            if sequence == parsed_sequence:
                return dict(lecture)

    selectors: list[str] = []
    if parsed_sequence is not None:
        selectors.append(f"sequence={parsed_sequence}")
    if cleaned_lecture_id:
        selectors.append(f"lecture_id={cleaned_lecture_id}")
    if cleaned_source_id:
        selectors.append(f"source_id={cleaned_source_id}")
    raise ValueError(f"No lecture matched {'; '.join(selectors)}")
