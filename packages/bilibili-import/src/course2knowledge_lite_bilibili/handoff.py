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
