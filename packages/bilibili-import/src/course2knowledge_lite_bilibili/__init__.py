from .collection import (
    BilibiliCollection,
    BilibiliCollectionUrl,
    BilibiliVideoRef,
    expand_bilibili_collection_url,
    is_bilibili_collection_url,
    parse_bilibili_collection_url,
)


def import_collection_skeleton_to_store(*args, **kwargs):
    from .handoff import import_collection_skeleton_to_store as _import_collection_skeleton_to_store

    return _import_collection_skeleton_to_store(*args, **kwargs)

__all__ = [
    "BilibiliCollection",
    "BilibiliCollectionUrl",
    "BilibiliVideoRef",
    "expand_bilibili_collection_url",
    "import_collection_skeleton_to_store",
    "is_bilibili_collection_url",
    "parse_bilibili_collection_url",
]
