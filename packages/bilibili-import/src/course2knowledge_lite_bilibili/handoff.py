from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from course2knowledge_lite_store import (
    SQLiteCourseStore,
    build_lite_lecture_dossier,
    build_course_skeleton,
    build_manual_transcript_segments,
    build_transcript_segments,
    render_lite_lecture_markdown,
)
from course2knowledge_lite_store.multimodal import (
    MultimodalConfigError,
    MultimodalDependencyError,
    MultimodalExtractionError,
    build_lite_anchor_frame_windows,
    build_lite_visual_evidence_records,
    copy_lite_keyframes_to_public_assets,
    extract_lite_candidate_frames_for_windows,
    select_lite_keyframes,
)

from .collection import JsonFetcher, expand_bilibili_source_url
from .parallelism import normalize_parallelism, resolve_lite_import_parallelism
from .subtitles import fetch_bilibili_timed_subtitles, probe_bilibili_subtitle_source


def import_collection_skeleton_to_store(
    source_url: str,
    *,
    store_root: str | Path,
    now: str | None = None,
    fetch_json: JsonFetcher | None = None,
    max_lectures: int | None = None,
) -> dict[str, Any]:
    collection = expand_bilibili_source_url(source_url, fetch_json=fetch_json)
    video_refs = collection.videos
    if max_lectures is not None:
        video_refs = video_refs[: max(int(max_lectures), 0)]
    skeleton = build_course_skeleton(
        title=collection.title,
        source_url=collection.source_url,
        video_refs=video_refs,
        now=now,
    )
    paths = SQLiteCourseStore(store_root).write_skeleton(skeleton)
    return {
        "course": skeleton.course.to_dict(),
        "lectures": [lecture.to_dict() for lecture in skeleton.lectures],
        "import_status": skeleton.import_status.to_dict(),
        "paths": paths,
    }


def import_collection_pipeline_to_store(
    source_url: str,
    *,
    store_root: str | Path,
    now: str | None = None,
    fetch_json: JsonFetcher | None = None,
    fetch_transcripts: bool = True,
    max_lectures: int | None = None,
    run_id: str = "",
    lecture_media_paths: dict[str, str] | None = None,
    public_repo_root: str | Path | None = None,
    compile_mode: str = "model",
    compile_provider: str | None = "deepseek",
    api_key: str | None = None,
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    lecture_workers: int = 1,
    apply_parallelism_profile: bool = True,
    source_kind: str = "bilibili_native_subtitle_pending",
    fast_map_mode: bool = True,
    split_map_mode: bool = True,
    fast_reduce_mode: bool = True,
    lite_map_mode: bool = False,
) -> dict[str, Any]:
    store = SQLiteCourseStore(store_root)
    if run_id:
        run = store.update_import_run(run_id, status="running", stage="collection_expand", now=now or "")
    else:
        run = store.create_import_run(
            course_id="",
            source_url=source_url,
            source_platform="bilibili",
            status="running",
            stage="collection_expand",
            now=now or "",
        )
        run_id = str(run["run_id"])
    store.append_import_event(
        run_id,
        stage="collection_expand",
        status="running",
        event_type="stage_start",
        message="Expanding Bilibili source",
        payload={"source_url": source_url},
        now=now or "",
    )
    try:
        skeleton_result = import_collection_skeleton_to_store(
            source_url,
            store_root=store_root,
            now=now,
            fetch_json=fetch_json,
            max_lectures=max_lectures,
        )
        course = dict(skeleton_result.get("course") or {})
        lectures = [dict(item) for item in skeleton_result.get("lectures") or []]
        course_id = str(course.get("course_id") or "")
        store.update_import_run(
            run_id,
            course_id=course_id,
            status="running",
            stage="source_acquisition",
            total_lectures=len(lectures),
            now=now or "",
        )
        store.record_import_artifact(
            run_id=run_id,
            course_id=course_id,
            artifact_type="course_skeleton",
            artifact_ref=f"sqlite://courses/{course_id}",
            status="ready",
            payload={"lecture_count": len(lectures)},
            now=now or "",
        )
        store.append_import_event(
            run_id,
            stage="collection_expand",
            status="completed",
            event_type="stage_completed",
            message="Course skeleton written",
            payload={"course_id": course_id, "lecture_count": len(lectures)},
            now=now or "",
        )

        completed = 0
        failed = 0
        requested_parallelism = normalize_parallelism(
            {
                "lecture_workers": lecture_workers,
                "dossier_chunk_workers": max_chunk_workers,
                "dossier_request_concurrency": max_concurrent_requests,
            }
        )
        parallelism_decision: dict[str, Any] = {
            "requested_parallelism": dict(requested_parallelism),
            "effective_parallelism": dict(requested_parallelism),
            "parallelism_profile": None,
            "parallelism_guard": None,
            "source_kind": source_kind,
            "selected_lecture_count": len(lectures),
        }
        if apply_parallelism_profile:
            parallelism_decision = resolve_lite_import_parallelism(
                requested_parallelism,
                source_kind=source_kind,
                selected_lecture_count=len(lectures),
                provider=compile_provider,
            )
        effective_parallelism = dict(parallelism_decision.get("effective_parallelism") or requested_parallelism)
        lecture_workers = max(1, min(int(effective_parallelism.get("lecture_workers") or 1), max(1, len(lectures))))
        max_chunk_workers = max(1, int(effective_parallelism.get("dossier_chunk_workers") or max_chunk_workers or 1))
        max_concurrent_requests = max(
            1,
            int(effective_parallelism.get("dossier_request_concurrency") or max_concurrent_requests or 1),
        )
        store.append_import_event(
            run_id,
            stage="lecture_compile",
            status="running",
            event_type="parallelism_resolved",
            message="Mother-style import parallelism profile resolved",
            payload={
                **parallelism_decision,
                "effective_parallelism": {
                    "lecture_workers": lecture_workers,
                    "dossier_chunk_workers": max_chunk_workers,
                    "dossier_request_concurrency": max_concurrent_requests,
                },
            },
            now=now or "",
        )

        def process_lecture(lecture: dict[str, Any]) -> dict[str, Any]:
            lecture_id = str(lecture.get("lecture_id") or "")
            worker_store = SQLiteCourseStore(store_root)
            if fetch_transcripts:
                transcript = import_lecture_transcript_to_store(
                    store_root=store_root,
                    course_id=course_id,
                    lecture=lecture,
                    fetch_json=fetch_json,
                )
                segment_count = int(transcript.get("segment_count") or 0)
            else:
                segment_count = len(worker_store.read_transcript_segments_if_exists(course_id, lecture_id))
                if segment_count <= 0:
                    raise RuntimeError("subtitle acquisition skipped and no transcript exists")
            worker_store.record_import_artifact(
                run_id=run_id,
                course_id=course_id,
                lecture_id=lecture_id,
                artifact_type="transcript",
                artifact_ref=f"sqlite://transcript_segments/{lecture_id}",
                status="ready",
                payload={"segment_count": segment_count},
                now=now or "",
            )
            note_result = _upsert_generated_lesson_note(
                worker_store,
                course_id=course_id,
                lecture=lecture,
                run_id=run_id,
                now=now or "",
                compile_mode=compile_mode,
                compile_provider=compile_provider,
                api_key=api_key,
                model=model,
                max_chunk_workers=max_chunk_workers,
                max_concurrent_requests=max_concurrent_requests,
                fast_map_mode=fast_map_mode,
                split_map_mode=split_map_mode,
                fast_reduce_mode=fast_reduce_mode,
                lite_map_mode=lite_map_mode,
            )
            note = dict(note_result["note"])
            worker_store.record_import_artifact(
                run_id=run_id,
                course_id=course_id,
                lecture_id=lecture_id,
                artifact_type="lesson_note",
                artifact_ref=f"sqlite://notes/{note['note_id']}",
                status="ready",
                payload={"note_id": note["note_id"]},
                now=now or "",
            )
            cards_result = worker_store.upsert_lecture_knowledge_cards_from_dossier(
                course_id,
                lecture=lecture,
                segments=worker_store.read_transcript_segments_if_exists(course_id, lecture_id),
                dossier=note_result["dossier"],
                overwrite=True,
            )
            worker_store.record_import_artifact(
                run_id=run_id,
                course_id=course_id,
                lecture_id=lecture_id,
                artifact_type="knowledge_atoms",
                artifact_ref=f"sqlite://knowledge_cards/{course_id}/{lecture_id}",
                status="ready" if cards_result.get("generated_card_count") else "empty",
                payload={
                    "card_count": int(cards_result.get("card_count") or 0),
                    "generated_card_count": int(cards_result.get("generated_card_count") or 0),
                    "compile_mode": compile_mode,
                    "compile_provider": compile_provider or "",
                },
                now=now or "",
            )
            visual_result = _upsert_lesson_visual_evidence(
                worker_store,
                store_root=store_root,
                course_id=course_id,
                lecture=lecture,
                dossier=note_result["dossier"],
                media_path=_lecture_media_path(lecture, lecture_media_paths or {}),
                run_id=run_id,
                public_repo_root=public_repo_root,
                now=now or "",
            )
            worker_store.record_import_artifact(
                run_id=run_id,
                course_id=course_id,
                lecture_id=lecture_id,
                artifact_type="visual_keyframes",
                artifact_ref=visual_result.get("artifact_ref", ""),
                status=str(visual_result.get("status") or "unavailable"),
                payload=dict(visual_result.get("payload") or {}),
                now=now or "",
            )
            return {
                "lecture": lecture,
                "lecture_id": lecture_id,
                "segment_count": segment_count,
            }

        def record_lecture_success(result: dict[str, Any]) -> None:
            nonlocal completed
            lecture = dict(result.get("lecture") or {})
            completed += 1
            store.append_import_event(
                run_id,
                stage="lecture_compile",
                status="completed",
                event_type="lecture_completed",
                message=f"Lecture {lecture.get('sequence')} transcript and note ready",
                payload={"lecture_id": result.get("lecture_id") or "", "segment_count": int(result.get("segment_count") or 0)},
                now=now or "",
            )
            store.update_import_run(
                run_id,
                status="running",
                stage="lecture_compile",
                completed_lectures=completed,
                failed_lectures=failed,
                now=now or "",
            )

        def record_lecture_failure(lecture: dict[str, Any], exc: Exception) -> None:
            nonlocal failed
            lecture_id = str(lecture.get("lecture_id") or "")
            failed += 1
            store.record_import_artifact(
                run_id=run_id,
                course_id=course_id,
                lecture_id=lecture_id,
                artifact_type="lecture_failure",
                artifact_ref="",
                status="failed",
                payload={"error_type": type(exc).__name__, "error": str(exc)},
                now=now or "",
            )
            store.append_import_event(
                run_id,
                stage="lecture_compile",
                status="failed",
                event_type="lecture_failed",
                message=f"Lecture {lecture.get('sequence')} is not ready",
                payload={"lecture_id": lecture_id, "error_type": type(exc).__name__, "error": str(exc)},
                now=now or "",
            )
            store.update_import_run(
                run_id,
                status="running",
                stage="lecture_compile",
                completed_lectures=completed,
                failed_lectures=failed,
                now=now or "",
            )

        def should_cancel() -> bool:
            if _import_run_cancelled(store, run_id):
                run = store.update_import_run(run_id, status="cancelled", stage="cancelled", now=now or "")
                store.append_import_event(
                    run_id,
                    stage="cancelled",
                    status="cancelled",
                    event_type="run_cancelled",
                    message="Import run was cancelled before the next lecture.",
                    payload={},
                    now=now or "",
                )
                return True
            return False

        if lecture_workers <= 1:
            for lecture in lectures:
                if should_cancel():
                    return {
                        **skeleton_result,
                        "status": "cancelled",
                        "run": store.read_import_run(run_id),
                        "run_id": run_id,
                        "readiness": store.summarize_import_readiness(course_id),
                        "events": store.list_import_events(run_id),
                        "artifacts": store.list_import_artifacts(run_id=run_id),
                    }
                try:
                    record_lecture_success(process_lecture(lecture))
                except Exception as exc:  # noqa: BLE001
                    record_lecture_failure(lecture, exc)
        else:
            with ThreadPoolExecutor(max_workers=lecture_workers) as executor:
                futures = {executor.submit(process_lecture, lecture): lecture for lecture in lectures}
                for future in as_completed(futures):
                    lecture = futures[future]
                    if _import_run_cancelled(store, run_id):
                        for pending in futures:
                            pending.cancel()
                        run = store.update_import_run(run_id, status="cancelled", stage="cancelled", now=now or "")
                        store.append_import_event(
                            run_id,
                            stage="cancelled",
                            status="cancelled",
                            event_type="run_cancelled",
                            message="Import run was cancelled while lecture workers were running.",
                            payload={},
                            now=now or "",
                        )
                        return {
                            **skeleton_result,
                            "status": "cancelled",
                            "run": run,
                            "run_id": run_id,
                            "readiness": store.summarize_import_readiness(course_id),
                            "events": store.list_import_events(run_id),
                            "artifacts": store.list_import_artifacts(run_id=run_id),
                        }
                    try:
                        record_lecture_success(future.result())
                    except Exception as exc:  # noqa: BLE001
                        record_lecture_failure(lecture, exc)

        readiness = store.summarize_import_readiness(course_id)
        final_status = "completed" if readiness["ready"] else ("partial" if completed > 0 else "failed")
        final_stage = "ready_gate" if readiness["ready"] else "ready_gate_blocked"
        run = store.update_import_run(
            run_id,
            status=final_status,
            stage=final_stage,
            completed_lectures=completed,
            failed_lectures=max(failed, int(readiness.get("missing_lecture_count") or 0)),
            now=now or "",
        )
        store.append_import_event(
            run_id,
            stage=final_stage,
            status=final_status,
            event_type="ready_gate",
            message="Course ready gate evaluated",
            payload={
                "ready": bool(readiness["ready"]),
                "ready_lecture_count": int(readiness.get("ready_lecture_count") or 0),
                "lecture_count": int(readiness.get("lecture_count") or 0),
                "missing_lecture_count": int(readiness.get("missing_lecture_count") or 0),
            },
            now=now or "",
        )
        return {
            **skeleton_result,
            "status": final_status,
            "run": run,
            "run_id": run_id,
            "readiness": readiness,
            "events": store.list_import_events(run_id),
            "artifacts": store.list_import_artifacts(run_id=run_id),
        }
    except Exception as exc:  # noqa: BLE001
        store.update_import_run(run_id, status="failed", stage="failed", now=now or "")
        store.append_import_event(
            run_id,
            stage="failed",
            status="failed",
            event_type="run_failed",
            message=str(exc),
            payload={"error_type": type(exc).__name__},
            now=now or "",
        )
        raise


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
    path = SQLiteCourseStore(store_root).write_transcript_segments(course_id, lecture_id, segments)
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
    store = SQLiteCourseStore(store_root)
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


def probe_lecture_transcript_source_by_reference(
    *,
    store_root: str | Path,
    course_id: str = "",
    import_id: str = "",
    lecture_sequence: int | str | None = None,
    lecture_id: str = "",
    source_id: str = "",
    fetch_json: JsonFetcher | None = None,
) -> dict[str, Any]:
    store = SQLiteCourseStore(store_root)
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
    return {
        "course_id": resolved_course_id,
        "import_id": cleaned_import_id,
        "lecture": lecture,
        "import_status": resolved_import_status,
        "subtitle_source": probe_bilibili_subtitle_source(str(lecture.get("source_url", "") or ""), fetch_json=fetch_json),
    }


def import_manual_transcript_by_reference_to_store(
    *,
    store_root: str | Path,
    transcript_text: str,
    course_id: str = "",
    import_id: str = "",
    lecture_sequence: int | str | None = None,
    lecture_id: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    store = SQLiteCourseStore(store_root)
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
    segments = build_manual_transcript_segments(lecture=lecture, transcript_text=transcript_text)
    path = store.write_transcript_segments(resolved_course_id, str(lecture["lecture_id"]), segments)
    return {
        "course_id": resolved_course_id,
        "import_id": cleaned_import_id,
        "lecture": lecture,
        "lecture_id": str(lecture["lecture_id"]),
        "source_id": str(lecture.get("source_id", "") or ""),
        "segment_count": len(segments),
        "path": path,
        "source_type": "manual_transcript_text",
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


def _upsert_generated_lesson_note(
    store: SQLiteCourseStore,
    *,
    course_id: str,
    lecture: dict[str, Any],
    run_id: str,
    now: str = "",
    compile_mode: str = "model",
    compile_provider: str | None = "deepseek",
    api_key: str | None = None,
    model: str | None = None,
    max_chunk_workers: int = 1,
    max_concurrent_requests: int = 1,
    fast_map_mode: bool = True,
    split_map_mode: bool = True,
    fast_reduce_mode: bool = True,
    lite_map_mode: bool = False,
) -> dict[str, Any]:
    lecture_id = str(lecture.get("lecture_id") or "")
    segments = store.read_transcript_segments_if_exists(course_id, lecture_id)
    if not segments:
        raise RuntimeError("lesson note requires transcript segments")
    note_id = f"generated_note_{lecture_id.replace(':', '_')}"
    course: dict[str, Any] = {}
    try:
        course = store.read_course(course_id)
    except Exception:  # noqa: BLE001
        course = {}
    dossier = build_lite_lecture_dossier(
        course=course,
        lecture=lecture,
        segments=segments,
        compile_mode=compile_mode,
        compile_provider=compile_provider,
        api_key=api_key,
        model=model,
        max_chunk_workers=max_chunk_workers,
        max_concurrent_requests=max_concurrent_requests,
        fast_map_mode=fast_map_mode,
        split_map_mode=split_map_mode,
        fast_reduce_mode=fast_reduce_mode,
        lite_map_mode=lite_map_mode,
    )
    body = render_lite_lecture_markdown(dossier, import_run_id=run_id)
    try:
        note = store.create_note(course_id, lecture_id, body, note_id=note_id, now=now)
    except ValueError as exc:
        if "note_id already exists" not in str(exc):
            raise
        note = store.update_note(course_id, note_id, body, now=now)
    return {"note": note, "dossier": dossier}


def _upsert_lesson_visual_evidence(
    store: SQLiteCourseStore,
    *,
    store_root: str | Path,
    course_id: str,
    lecture: dict[str, Any],
    media_path: str,
    dossier: Any | None = None,
    run_id: str,
    public_repo_root: str | Path | None = None,
    now: str = "",
) -> dict[str, Any]:
    lecture_id = str(lecture.get("lecture_id") or "")
    segments = store.read_transcript_segments_if_exists(course_id, lecture_id)
    if not segments:
        return {
            "status": "unavailable",
            "artifact_ref": "",
            "payload": {"reason": "missing_transcript_segments"},
        }
    if not str(media_path or "").strip():
        return {
            "status": "unavailable",
            "artifact_ref": "",
            "payload": {"reason": "missing_source_media", "mode": "local_media_path_required"},
        }
    course = {}
    try:
        course = store.read_course(course_id)
    except Exception:  # noqa: BLE001
        course = {}
    if dossier is None:
        dossier = build_lite_lecture_dossier(course=course, lecture=lecture, segments=segments)
    windows = build_lite_anchor_frame_windows(anchors=dossier.to_dict()["anchors"], lead_seconds=2.0, lag_seconds=4.0)
    if not windows:
        return {
            "status": "unavailable",
            "artifact_ref": "",
            "payload": {"reason": "no_visual_anchor_windows"},
        }
    repo_root = Path(public_repo_root).expanduser().resolve() if public_repo_root else Path(__file__).resolve().parents[4]
    output_root = (
        repo_root
        / "tmp"
        / "generated-keyframes-work"
        / _safe_path_id(run_id)
        / _safe_path_id(lecture_id)
    )
    try:
        candidates = extract_lite_candidate_frames_for_windows(
            media_path=media_path,
            windows=windows,
            output_root=str(output_root),
            sample_every_seconds=0.5,
        )
        selected = select_lite_keyframes(candidates)
        if not selected:
            return {
                "status": "unavailable",
                "artifact_ref": "",
                "payload": {"reason": "no_candidate_frames", "window_count": len(windows)},
            }
        public_paths = copy_lite_keyframes_to_public_assets(
            keyframes=selected,
            repo_root=str(repo_root),
            course_id=course_id,
            lecture_id=lecture_id,
        )
        visual_records = build_lite_visual_evidence_records(
            course_id=course_id,
            lecture=lecture,
            anchors=dossier.to_dict()["anchors"],
            keyframe_paths=public_paths,
            now=now,
        )
        store.upsert_visual_evidence_records(course_id, visual_records)
        return {
            "status": "ready",
            "artifact_ref": f"sqlite://visual_evidence/{course_id}/{lecture_id}",
            "payload": {
                "visual_count": len(visual_records),
                "window_count": len(windows),
                "image_paths": [record["image_path"] for record in visual_records],
                "provenance": "generated_keyframe",
            },
        }
    except (MultimodalConfigError, MultimodalDependencyError, MultimodalExtractionError) as exc:
        return {
            "status": "unavailable",
            "artifact_ref": "",
            "payload": {"reason": type(exc).__name__, "message": str(exc)},
        }


def _lecture_media_path(lecture: dict[str, Any], media_paths: dict[str, str]) -> str:
    keys = [
        str(lecture.get("lecture_id") or "").strip(),
        str(lecture.get("source_id") or "").strip(),
        str(lecture.get("sequence") or "").strip(),
        str(lecture.get("source_url") or "").strip(),
    ]
    for key in keys:
        if key and str(media_paths.get(key) or "").strip():
            return str(media_paths[key]).strip()
    return ""


def _safe_path_id(raw_value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(raw_value or "").strip())
    return cleaned.strip("._") or "item"


def _import_run_cancelled(store: SQLiteCourseStore, run_id: str) -> bool:
    try:
        return str(store.read_import_run(run_id).get("status") or "") == "cancelled"
    except Exception:  # noqa: BLE001
        return False
