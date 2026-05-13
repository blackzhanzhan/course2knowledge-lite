from __future__ import annotations

from pathlib import Path
from typing import Any

from course2knowledge_lite_store import JsonCourseStore, build_course_skeleton

from .collection import JsonFetcher, expand_bilibili_collection_url


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
