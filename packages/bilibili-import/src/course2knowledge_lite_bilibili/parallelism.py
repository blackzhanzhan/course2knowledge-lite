from __future__ import annotations

from typing import Any


DEFAULT_IMPORT_PARALLELISM = {
    "lecture_workers": 10,
    "dossier_chunk_workers": 8,
    "dossier_request_concurrency": 80,
}
LARGE_COURSE_PROFILE_THRESHOLD = 64
LARGE_COURSE_PARALLELISM = {
    "lecture_workers": 12,
    "dossier_chunk_workers": 8,
    "dossier_request_concurrency": 8,
}
DEEPSEEK_FLASH_PARALLELISM = {
    "lecture_workers": 10,
    "dossier_chunk_workers": 8,
    "dossier_request_concurrency": 40,
}
COLLECTION_SOURCE_KINDS = {
    "collection",
    "explicit_collection",
    "video_page_collection",
    "bilibili_native_subtitle_pending",
}


def normalize_parallelism(parallelism: dict[str, Any] | None) -> dict[str, int]:
    payload = dict(DEFAULT_IMPORT_PARALLELISM)
    payload.update(dict(parallelism or {}))
    return {
        "lecture_workers": max(1, int(payload.get("lecture_workers", 1) or 1)),
        "dossier_chunk_workers": max(1, int(payload.get("dossier_chunk_workers", 1) or 1)),
        "dossier_request_concurrency": max(1, int(payload.get("dossier_request_concurrency", 1) or 1)),
    }


def resolve_large_course_parallelism_profile(
    parallelism: dict[str, Any],
    *,
    source_kind: str,
    selected_lecture_count: int,
) -> tuple[dict[str, int], dict[str, Any] | None]:
    requested = normalize_parallelism(parallelism)
    cleaned_source_kind = str(source_kind or "").strip()
    if cleaned_source_kind not in COLLECTION_SOURCE_KINDS:
        return dict(requested), None
    if int(selected_lecture_count or 0) < LARGE_COURSE_PROFILE_THRESHOLD:
        return dict(requested), None
    effective = {key: int(value) for key, value in LARGE_COURSE_PARALLELISM.items()}
    return effective, {
        "profile_id": "large_course",
        "source_kind": cleaned_source_kind,
        "selected_lecture_count": int(selected_lecture_count or 0),
        "requested_parallelism": requested,
        "effective_parallelism": effective,
    }


def apply_parallelism_guard(
    parallelism: dict[str, Any],
    *,
    source_kind: str,
    provider: str | None,
) -> tuple[dict[str, int], dict[str, Any] | None]:
    requested = normalize_parallelism(parallelism)
    cleaned_provider = str(provider or "").strip().lower()
    if cleaned_provider != "deepseek":
        return dict(requested), None
    effective = {
        key: min(int(requested[key]), int(limit))
        for key, limit in DEEPSEEK_FLASH_PARALLELISM.items()
    }
    if effective == requested:
        return effective, None
    return effective, {
        "guard_id": "deepseek_flash_profile",
        "provider": cleaned_provider,
        "source_kind": str(source_kind or "").strip(),
        "reason": "DeepSeek Flash uses a capped request fan-out profile to keep lecture-dossier compilation bounded.",
        "requested_parallelism": requested,
        "effective_parallelism": effective,
    }


def resolve_lite_import_parallelism(
    parallelism: dict[str, Any] | None,
    *,
    source_kind: str,
    selected_lecture_count: int,
    provider: str | None,
) -> dict[str, Any]:
    requested = normalize_parallelism(parallelism)
    profiled, profile = resolve_large_course_parallelism_profile(
        requested,
        source_kind=source_kind,
        selected_lecture_count=selected_lecture_count,
    )
    effective, guard = apply_parallelism_guard(
        profiled,
        source_kind=source_kind,
        provider=provider,
    )
    return {
        "requested_parallelism": requested,
        "effective_parallelism": effective,
        "parallelism_profile": profile,
        "parallelism_guard": guard,
        "source_kind": str(source_kind or "").strip(),
        "selected_lecture_count": int(selected_lecture_count or 0),
    }

