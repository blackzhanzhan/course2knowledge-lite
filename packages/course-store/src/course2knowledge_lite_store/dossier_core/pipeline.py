from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1
from typing import Any, Iterable

from .adapters import RequestRetryTelemetryRecorder, format_timestamp_anchor
from .contracts import (
    normalize_anchor,
    normalize_atom,
    normalize_feedback_route,
    normalize_followup_scaffold,
    normalize_relation,
    normalize_search_hook,
    normalize_tutoring_example,
    normalize_tutoring_pitfall,
    normalize_tutoring_prerequisite,
    serialize_anchor,
    serialize_atom,
    serialize_relation,
)
from .deepseek import DEEPSEEK_MODEL
from .pipeline_tutoring import enrich_tutoring_fields
from .text_map import map_subtitle_chunk
from .text_reduce import (
    DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
    FAST_REDUCE_MAX_TOKENS,
    build_input_guarded_reduce_payload,
    reduce_mapped_chunks,
)


def compile_lite_lecture_dossier_from_segments(
    *,
    course_name: str,
    lecture_id: str,
    lecture_title: str,
    source_url: str,
    segments: Iterable[dict[str, Any]],
    provider: str = "course2knowledge_lite_model_compile",
    compile_provider: str | None = None,
    map_compile_provider: str | None = None,
    reduce_compile_provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    reduce_max_tokens: int = DEFAULT_LECTURE_DOSSIER_DEEPSEEK_MAX_TOKENS,
    max_lines_per_chunk: int = 80,
    overlap_lines: int = 4,
    max_chars_per_chunk: int = 1800,
    map_request_concurrency: int | None = None,
    fast_map_mode: bool = False,
    split_map_mode: bool = False,
    fast_reduce_mode: bool = False,
    lite_map_mode: bool = False,
    multimodal_mode: str = "disabled",
) -> dict[str, Any]:
    """Compile a mother-shaped lecture dossier from child-local transcript rows."""

    cleaned_segments = _normalize_segments(segments)
    if not cleaned_segments:
        raise ValueError("model lecture dossier compile requires transcript segments")

    effective_map_provider = _resolve_stage_provider(map_compile_provider, compile_provider)
    effective_reduce_provider = _resolve_stage_provider(reduce_compile_provider, compile_provider)
    chunk_manifest = _build_chunk_manifest(
        lecture_id=lecture_id,
        segments=cleaned_segments,
        max_lines_per_chunk=max_lines_per_chunk,
        overlap_lines=overlap_lines,
        max_chars_per_chunk=max_chars_per_chunk,
    )
    mapped_chunks: list[dict[str, Any]] = []
    telemetry_recorder = RequestRetryTelemetryRecorder()
    effective_map_request_concurrency = (
        max(1, int(map_request_concurrency))
        if map_request_concurrency is not None
        else max(1, int(max_concurrent_requests or 1))
    )
    artifact_ref = f"sqlite://lecture_dossier/{lecture_id}"

    def run_map(chunk: dict[str, Any]) -> dict[str, Any]:
        if lite_map_mode:
            text = str(chunk.get("text") or "").strip()
            return {
                "chunk_id": str(chunk.get("chunk_id") or ""),
                "chunk_summary": text[:120],
                "anchors": [
                    {
                        "anchor_id": f"{chunk['chunk_id']}_anc_001",
                        "modality": "subtitle",
                        "source_line_ids": list(chunk.get("source_line_ids") or []),
                        "start_timestamp": str(chunk.get("start_timestamp") or ""),
                        "end_timestamp": str(chunk.get("end_timestamp") or ""),
                        "suggested_screenshot_timestamp": str(chunk.get("start_timestamp") or ""),
                        "evidence_quote": text[:160],
                        "confidence": 0.45,
                    }
                ],
                "atoms": [],
                "relations": [],
            }
        raw_payload, maybe_normalized = _unwrap_worker_result(
            map_subtitle_chunk(
                course_name=course_name,
                lecture_title=lecture_title,
                source_url=source_url,
                chunk=chunk,
                api_key=api_key,
                model=model or DEEPSEEK_MODEL,
                max_concurrent_requests=effective_map_request_concurrency,
                telemetry_recorder=telemetry_recorder,
                request_label=f"map:{chunk['chunk_id']}",
                fast_map_mode=fast_map_mode,
                split_map_mode=split_map_mode,
                compile_provider=effective_map_provider,
                source_kind="sqlite_transcript_segments",
                multimodal_mode=multimodal_mode,
            )
        )
        return _normalize_map_result(
            raw_payload=maybe_normalized,
            chunk=chunk,
            artifact_ref=artifact_ref,
        )

    chunks = list(chunk_manifest.get("chunks") or [])
    if max_chunk_workers <= 1 or lite_map_mode:
        for chunk in chunks:
            mapped_chunks.append(run_map(chunk))
    else:
        with ThreadPoolExecutor(max_workers=max(1, int(max_chunk_workers or 1))) as executor:
            mapped_chunks.extend(executor.map(run_map, chunks))

    compact_reduce_payload, reduce_guard = build_input_guarded_reduce_payload(
        course_name=course_name,
        lecture_title=lecture_title,
        source_url=source_url,
        mapped_chunks=mapped_chunks,
        fast_reduce_mode=fast_reduce_mode,
    )
    effective_reduce_max_tokens = (
        min(int(reduce_max_tokens), FAST_REDUCE_MAX_TOKENS)
        if fast_reduce_mode
        else int(reduce_max_tokens)
    )
    raw_reduce_payload, maybe_normalized_reduce = _unwrap_worker_result(
        reduce_mapped_chunks(
            course_name=course_name,
            lecture_title=lecture_title,
            source_url=source_url,
            mapped_chunks=mapped_chunks,
            compact_mapped_chunks=compact_reduce_payload,
            api_key=api_key,
            model=model or DEEPSEEK_MODEL,
            max_tokens=effective_reduce_max_tokens,
            max_concurrent_requests=max(1, int(max_concurrent_requests or 1)),
            telemetry_recorder=telemetry_recorder,
            request_label="reduce",
            compile_provider=effective_reduce_provider,
            source_kind="sqlite_transcript_segments",
            multimodal_mode=multimodal_mode,
            lite_map_mode=lite_map_mode,
        )
    )
    normalized_reduce_payload = _normalize_reduce_result(
        raw_payload=maybe_normalized_reduce,
        lecture_title=lecture_title,
    )

    deduped_anchors: dict[str, dict[str, Any]] = {}
    deduped_atoms: dict[str, dict[str, Any]] = {}
    deduped_relations: dict[str, dict[str, Any]] = {}
    for mapped_chunk in mapped_chunks:
        for anchor in mapped_chunk.get("anchors") or []:
            anchor_id = str(anchor.get("anchor_id") or "")
            if anchor_id:
                deduped_anchors[anchor_id] = anchor
        for atom in mapped_chunk.get("atoms") or []:
            atom_id = str(atom.get("atom_id") or atom.get("canonical_title") or "")
            if atom_id:
                deduped_atoms[atom_id] = atom
        for relation in mapped_chunk.get("relations") or []:
            relation_id = str(relation.get("relation_id") or "")
            if relation_id:
                deduped_relations[relation_id] = relation

    tutoring_payload = enrich_tutoring_fields(
        tutoring_payload=normalized_reduce_payload,
        course_name=course_name,
        lecture_title=normalized_reduce_payload["lecture_title"],
        atoms=list(deduped_atoms.values()),
        relations=list(deduped_relations.values()),
        anchors=list(deduped_anchors.values()),
    )
    return {
        "schema_version": "lite_lecture_dossier.mother_shape.v1",
        "course_title": course_name,
        "course_name": course_name,
        "lecture_id": lecture_id,
        "lecture_title": normalized_reduce_payload["lecture_title"],
        "source_url": source_url,
        "provider": provider,
        "compile_source": "model_map_reduce",
        "subtitle_source_kind": "transcript_segments",
        "lecture_summary": normalized_reduce_payload["lecture_summary"],
        "sections": normalized_reduce_payload["sections"],
        "anchors": list(deduped_anchors.values()),
        "atoms": list(deduped_atoms.values()),
        "relations": list(deduped_relations.values()),
        "review_questions": list(tutoring_payload.get("review_questions") or normalized_reduce_payload["review_questions"]),
        "prerequisites": [
            dict(item)
            for item in tutoring_payload.get("prerequisites") or normalized_reduce_payload["prerequisites"]
            if isinstance(item, dict)
        ],
        "pitfalls": [
            dict(item)
            for item in tutoring_payload.get("pitfalls") or normalized_reduce_payload["pitfalls"]
            if isinstance(item, dict)
        ],
        "minimal_checks": [
            dict(item)
            for item in tutoring_payload.get("minimal_checks") or []
            if isinstance(item, dict)
        ],
        "minimal_examples": [
            dict(item)
            for item in tutoring_payload.get("minimal_examples") or normalized_reduce_payload["minimal_examples"]
            if isinstance(item, dict)
        ],
        "followup_scaffold": [
            dict(item)
            for item in tutoring_payload.get("followup_scaffold") or []
            if isinstance(item, dict)
        ],
        "feedback_routes": [
            dict(item)
            for item in tutoring_payload.get("feedback_routes") or []
            if isinstance(item, dict)
        ],
        "search_hooks": [
            dict(item)
            for item in tutoring_payload.get("search_hooks") or []
            if isinstance(item, dict)
        ],
        "compile_report": {
            "chunk_count": int(chunk_manifest.get("chunk_count") or 0),
            "mapped_chunk_count": len(mapped_chunks),
            "anchor_count": len(deduped_anchors),
            "atom_count": len(deduped_atoms),
            "relation_count": len(deduped_relations),
            "telemetry": [dict(item) for item in telemetry_recorder.records],
            "reduce_guard": dict(reduce_guard),
        },
        "_raw_reduce_payload": raw_reduce_payload,
    }


def _resolve_stage_provider(stage_override: str | None, fallback: str | None) -> str | None:
    explicit = str(stage_override or "").strip()
    if explicit and explicit != "auto":
        return explicit
    return fallback


def _normalize_segments(segments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(segments, start=1):
        if not isinstance(raw, dict):
            continue
        text = " ".join(str(raw.get("text") or "").split())
        if not text:
            continue
        normalized.append(
            {
                "line_id": index,
                "segment_id": str(raw.get("segment_id") or f"seg_{index:05d}").strip(),
                "lecture_id": str(raw.get("lecture_id") or "").strip(),
                "start_seconds": float(raw.get("start_seconds") or 0.0),
                "end_seconds": float(raw.get("end_seconds") or raw.get("start_seconds") or 0.0),
                "text": text,
            }
        )
    return normalized


def _build_chunk_manifest(
    *,
    lecture_id: str,
    segments: list[dict[str, Any]],
    max_lines_per_chunk: int,
    overlap_lines: int,
    max_chars_per_chunk: int,
) -> dict[str, Any]:
    step = max(1, int(max_lines_per_chunk or 1) - max(0, int(overlap_lines or 0)))
    chunks: list[dict[str, Any]] = []
    start_index = 0
    while start_index < len(segments):
        chunk_lines = segments[start_index : start_index + max(1, int(max_lines_per_chunk or 1))]
        while len(chunk_lines) > 1:
            chunk_text = "\n".join(str(line["text"]) for line in chunk_lines)
            if len(chunk_text) <= max_chars_per_chunk:
                break
            chunk_lines = chunk_lines[:-1]
        if not chunk_lines:
            break
        source_line_ids = [int(line["line_id"]) for line in chunk_lines]
        chunk_start_seconds = float(chunk_lines[0]["start_seconds"])
        chunk_end_seconds = float(chunk_lines[-1]["end_seconds"])
        chunks.append(
            {
                "chunk_id": f"chunk_{len(chunks) + 1:03d}",
                "source_line_ids": source_line_ids,
                "line_start": source_line_ids[0],
                "line_end": source_line_ids[-1],
                "start_timestamp": format_timestamp_anchor(chunk_start_seconds),
                "end_timestamp": format_timestamp_anchor(chunk_end_seconds),
                "text": "\n".join(str(line["text"]) for line in chunk_lines),
                "line_count": len(chunk_lines),
                "char_count": len("".join(str(line["text"]) for line in chunk_lines)),
            }
        )
        if source_line_ids[-1] >= len(segments):
            break
        start_index += step
    return {"lecture_id": lecture_id, "chunk_count": len(chunks), "chunks": chunks}


def _unwrap_worker_result(payload: tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(payload, tuple) and len(payload) == 2:
        raw_payload, normalized_payload = payload
        return raw_payload, normalized_payload
    if isinstance(payload, dict):
        return payload, payload
    raise TypeError(f"Unsupported lecture dossier worker result: {type(payload)!r}")


def _normalize_map_result(
    *,
    raw_payload: dict[str, Any],
    chunk: dict[str, Any],
    artifact_ref: str,
) -> dict[str, Any]:
    chunk_source_line_ids = tuple(
        int(item)
        for item in (chunk.get("source_line_ids") or [])
        if str(item).strip()
    )
    chunk_text_lines = [
        str(item).strip()
        for item in str(chunk.get("text", "") or "").splitlines()
    ]
    chunk_line_text_by_id = {
        line_id: chunk_text_lines[index]
        for index, line_id in enumerate(chunk_source_line_ids)
        if index < len(chunk_text_lines)
    }

    def iter_dict_items(raw_items: Any):
        if isinstance(raw_items, dict):
            iterable = raw_items.values()
        elif isinstance(raw_items, (list, tuple)):
            iterable = raw_items
        else:
            return
        for item in iterable:
            if isinstance(item, dict):
                yield item

    def salvage_evidence_quote(raw_anchor: dict[str, Any]) -> dict[str, Any]:
        if str(raw_anchor.get("evidence_quote", "") or "").strip():
            return raw_anchor
        source_line_ids: list[int] = []
        for item in raw_anchor.get("source_line_ids") or chunk_source_line_ids[:8]:
            try:
                source_line_ids.append(int(item))
            except (TypeError, ValueError):
                continue
        quote = " ".join(
            chunk_line_text_by_id.get(line_id, "")
            for line_id in source_line_ids[:8]
        ).strip()
        if not quote:
            quote = str(chunk.get("text", "") or "").replace("\n", " ").strip()
        patched_anchor = dict(raw_anchor)
        patched_anchor["evidence_quote"] = quote[:120] or f"line {chunk_source_line_ids[0] if chunk_source_line_ids else 1}"
        patched_anchor["needs_human_review"] = True
        patched_anchor.setdefault("source_line_ids", source_line_ids or list(chunk_source_line_ids[:8]))
        return patched_anchor

    normalized_anchors = []
    for index, raw_anchor in enumerate(iter_dict_items(raw_payload.get("anchors")), start=1):
        anchor = normalize_anchor(
            salvage_evidence_quote(raw_anchor),
            default_anchor_id=f"{chunk['chunk_id']}_anc_{index:03d}",
            default_source_line_ids=chunk_source_line_ids,
            default_start_timestamp=str(chunk.get("start_timestamp", "")).strip(),
            default_end_timestamp=str(chunk.get("end_timestamp", "")).strip(),
            default_suggested_timestamp=str(chunk.get("start_timestamp", "")).strip(),
        )
        normalized_anchors.append(serialize_anchor(anchor))

    normalized_atoms = [
        serialize_atom(normalize_atom(raw_atom, artifact_ref=artifact_ref))
        for raw_atom in iter_dict_items(raw_payload.get("atoms"))
    ]
    normalized_relations = [
        serialize_relation(normalize_relation(raw_relation))
        for raw_relation in iter_dict_items(raw_payload.get("relations"))
    ]
    return {
        "chunk_id": str(chunk["chunk_id"]),
        "chunk_summary": str(raw_payload.get("chunk_summary", "")).strip(),
        "anchors": normalized_anchors,
        "atoms": normalized_atoms,
        "relations": normalized_relations,
    }


def _normalize_reduce_result(
    *,
    raw_payload: dict[str, Any],
    lecture_title: str,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for item in raw_payload.get("sections") or []:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading", "")).strip()
        if not heading:
            continue
        sections.append(
            {
                "heading": heading,
                "body": str(item.get("body", "")).strip(),
                "anchor_ids": [
                    str(value).strip()
                    for value in item.get("anchor_ids") or []
                    if str(value).strip()
                ],
            }
        )
    return {
        "lecture_title": str(raw_payload.get("lecture_title", "")).strip() or lecture_title,
        "lecture_summary": str(raw_payload.get("lecture_summary", "")).strip(),
        "sections": sections,
        "review_questions": [
            str(item).strip()
            for item in raw_payload.get("review_questions") or []
            if str(item).strip()
        ],
        "prerequisites": [
            item
            for item in (
                normalize_tutoring_prerequisite(raw_item)
                for raw_item in raw_payload.get("prerequisites") or []
            )
            if item is not None
        ],
        "pitfalls": [
            item
            for item in (
                normalize_tutoring_pitfall(raw_item)
                for raw_item in raw_payload.get("pitfalls") or []
            )
            if item is not None
        ],
        "minimal_examples": [
            item
            for item in (
                normalize_tutoring_example(raw_item)
                for raw_item in raw_payload.get("minimal_examples") or []
            )
            if item is not None
        ],
        "followup_scaffold": [
            item
            for item in (
                normalize_followup_scaffold(raw_item)
                for raw_item in raw_payload.get("followup_scaffold") or []
            )
            if item is not None
        ],
        "feedback_routes": [
            item
            for item in (
                normalize_feedback_route(raw_item)
                for raw_item in raw_payload.get("feedback_routes") or []
            )
            if item is not None
        ],
        "search_hooks": [
            item
            for item in (
                normalize_search_hook(raw_item)
                for raw_item in raw_payload.get("search_hooks") or []
            )
            if item is not None
        ],
    }


def stable_lite_lecture_id(*, course_name: str, source_url: str, lecture_title: str) -> str:
    seed = f"{course_name}|{source_url}|{lecture_title}".encode("utf-8")
    return sha1(seed).hexdigest()[:12]
