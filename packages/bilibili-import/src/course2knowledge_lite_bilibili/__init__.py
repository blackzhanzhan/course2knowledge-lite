from .collection import (
    BilibiliCollection,
    BilibiliCollectionUrl,
    BilibiliVideoRef,
    expand_bilibili_collection_url,
    expand_bilibili_source_url,
    expand_bilibili_video_url,
    extract_bilibili_bvid,
    is_bilibili_collection_url,
    is_bilibili_video_url,
    parse_bilibili_collection_url,
)
from .subtitles import (
    BilibiliPageMetadata,
    BilibiliTimedSubtitle,
    build_bilibili_json_fetcher,
    extract_bilibili_bvid_and_page,
    fetch_bilibili_timed_subtitles,
    probe_bilibili_subtitle_source,
    redact_bilibili_cookie,
    resolve_bilibili_page_metadata,
)
from .parallelism import (
    DEFAULT_IMPORT_PARALLELISM,
    DEEPSEEK_FLASH_PARALLELISM,
    LARGE_COURSE_PARALLELISM,
    LARGE_COURSE_PROFILE_THRESHOLD,
    apply_parallelism_guard,
    resolve_large_course_parallelism_profile,
    resolve_lite_import_parallelism,
)


def import_collection_skeleton_to_store(*args, **kwargs):
    from .handoff import import_collection_skeleton_to_store as _import_collection_skeleton_to_store

    return _import_collection_skeleton_to_store(*args, **kwargs)


def import_collection_pipeline_to_store(*args, **kwargs):
    from .handoff import import_collection_pipeline_to_store as _import_collection_pipeline_to_store

    return _import_collection_pipeline_to_store(*args, **kwargs)


def import_lecture_transcript_to_store(*args, **kwargs):
    from .handoff import import_lecture_transcript_to_store as _import_lecture_transcript_to_store

    return _import_lecture_transcript_to_store(*args, **kwargs)


def import_lecture_transcript_by_reference_to_store(*args, **kwargs):
    from .handoff import (
        import_lecture_transcript_by_reference_to_store as _import_lecture_transcript_by_reference_to_store,
    )

    return _import_lecture_transcript_by_reference_to_store(*args, **kwargs)


def import_manual_transcript_by_reference_to_store(*args, **kwargs):
    from .handoff import import_manual_transcript_by_reference_to_store as _import_manual_transcript_by_reference_to_store

    return _import_manual_transcript_by_reference_to_store(*args, **kwargs)


def probe_lecture_transcript_source_by_reference(*args, **kwargs):
    from .handoff import probe_lecture_transcript_source_by_reference as _probe_lecture_transcript_source_by_reference

    return _probe_lecture_transcript_source_by_reference(*args, **kwargs)

__all__ = [
    "BilibiliCollection",
    "BilibiliCollectionUrl",
    "BilibiliPageMetadata",
    "BilibiliTimedSubtitle",
    "BilibiliVideoRef",
    "DEFAULT_IMPORT_PARALLELISM",
    "DEEPSEEK_FLASH_PARALLELISM",
    "LARGE_COURSE_PARALLELISM",
    "LARGE_COURSE_PROFILE_THRESHOLD",
    "apply_parallelism_guard",
    "build_bilibili_json_fetcher",
    "expand_bilibili_collection_url",
    "expand_bilibili_source_url",
    "expand_bilibili_video_url",
    "extract_bilibili_bvid",
    "extract_bilibili_bvid_and_page",
    "fetch_bilibili_timed_subtitles",
    "import_collection_pipeline_to_store",
    "import_collection_skeleton_to_store",
    "import_lecture_transcript_by_reference_to_store",
    "import_lecture_transcript_to_store",
    "import_manual_transcript_by_reference_to_store",
    "is_bilibili_collection_url",
    "is_bilibili_video_url",
    "parse_bilibili_collection_url",
    "probe_bilibili_subtitle_source",
    "probe_lecture_transcript_source_by_reference",
    "redact_bilibili_cookie",
    "resolve_bilibili_page_metadata",
    "resolve_large_course_parallelism_profile",
    "resolve_lite_import_parallelism",
]
