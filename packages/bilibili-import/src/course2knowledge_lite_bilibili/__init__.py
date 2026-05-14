from .collection import (
    BilibiliCollection,
    BilibiliCollectionUrl,
    BilibiliVideoRef,
    expand_bilibili_collection_url,
    is_bilibili_collection_url,
    parse_bilibili_collection_url,
)
from .subtitles import (
    BilibiliPageMetadata,
    BilibiliTimedSubtitle,
    extract_bilibili_bvid_and_page,
    fetch_bilibili_timed_subtitles,
    resolve_bilibili_page_metadata,
)


def import_collection_skeleton_to_store(*args, **kwargs):
    from .handoff import import_collection_skeleton_to_store as _import_collection_skeleton_to_store

    return _import_collection_skeleton_to_store(*args, **kwargs)


def import_lecture_transcript_to_store(*args, **kwargs):
    from .handoff import import_lecture_transcript_to_store as _import_lecture_transcript_to_store

    return _import_lecture_transcript_to_store(*args, **kwargs)


def import_lecture_transcript_by_reference_to_store(*args, **kwargs):
    from .handoff import (
        import_lecture_transcript_by_reference_to_store as _import_lecture_transcript_by_reference_to_store,
    )

    return _import_lecture_transcript_by_reference_to_store(*args, **kwargs)

__all__ = [
    "BilibiliCollection",
    "BilibiliCollectionUrl",
    "BilibiliPageMetadata",
    "BilibiliTimedSubtitle",
    "BilibiliVideoRef",
    "expand_bilibili_collection_url",
    "extract_bilibili_bvid_and_page",
    "fetch_bilibili_timed_subtitles",
    "import_collection_skeleton_to_store",
    "import_lecture_transcript_by_reference_to_store",
    "import_lecture_transcript_to_store",
    "is_bilibili_collection_url",
    "parse_bilibili_collection_url",
    "resolve_bilibili_page_metadata",
]
