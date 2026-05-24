from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Iterator
from uuid import uuid4

from .content import build_lecture_reader_payload, search_transcript_segments
from .models import (
    CHAT_EVENT_TYPES,
    CHAT_MESSAGE_ROLES,
    IMPORT_RUN_STATUSES,
    READING_PROGRESS_STATUSES,
    BookmarkRecord,
    ChatEventRecord,
    ChatMessageRecord,
    ChatThreadRecord,
    CourseSkeleton,
    ImportArtifactRecord,
    ImportEventRecord,
    ImportRunRecord,
    KnowledgeCardRecord,
    NoteRecord,
    ReadingProgressRecord,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
    WEB_COURSE_BINDING_STATUSES,
    WebCourseBindingRecord,
)
from .lecture_dossier import build_lite_lecture_dossier, filter_lite_quality_atoms, lite_atom_quality
from .store import (
    _anchor_segment_ids_from_dossier,
    _card_atoms_from_dossier,
    _card_tags,
    _card_title,
    _is_generated_card,
    _knowledge_atom_specs,
    _query_terms,
    _segment_ids_for_atom,
    _visual_search_matches,
)


DEFAULT_SQLITE_FILENAME = "course2knowledge-lite.sqlite3"


class SQLiteCourseStore:
    def __init__(self, root: str | Path) -> None:
        configured = Path(root).expanduser()
        if configured.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            self.db_path = configured
            self.root = configured.parent
        else:
            self.root = configured
            self.db_path = self.root / DEFAULT_SQLITE_FILENAME
        self.root.mkdir(parents=True, exist_ok=True)

    def write_skeleton(self, skeleton: CourseSkeleton) -> dict[str, str]:
        course = skeleton.course.to_dict()
        lectures = [lecture.to_dict() for lecture in skeleton.lectures]
        import_status = skeleton.import_status.to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO courses
                (course_id, title, source_url, source_platform, import_status, created_at, updated_at)
                VALUES (:course_id, :title, :source_url, :source_platform, :import_status, :created_at, :updated_at)
                """,
                course,
            )
            conn.execute("DELETE FROM lectures WHERE course_id = ?", (skeleton.course.course_id,))
            conn.executemany(
                """
                INSERT INTO lectures
                (lecture_id, course_id, title, source_url, source_id, sequence, duration_seconds, read_status)
                VALUES (:lecture_id, :course_id, :title, :source_url, :source_id, :sequence, :duration_seconds, :read_status)
                """,
                lectures,
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO import_statuses
                (import_id, course_id, source_url, source_platform, status, stage, total_lectures,
                 completed_lectures, failed_lectures, created_at, updated_at)
                VALUES (:import_id, :course_id, :source_url, :source_platform, :status, :stage, :total_lectures,
                        :completed_lectures, :failed_lectures, :created_at, :updated_at)
                """,
                import_status,
            )
        return {
            "database": str(self.db_path),
            "course": f"{self.db_path}::courses/{skeleton.course.course_id}",
            "lectures": f"{self.db_path}::lectures/{skeleton.course.course_id}",
            "import_status": f"{self.db_path}::import_statuses/{skeleton.import_status.import_id}",
        }

    def read_course(self, course_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM courses WHERE course_id = ?", (course_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"course not found: {course_id}")
        return _dict(row)

    def read_lectures(self, course_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM lectures WHERE course_id = ? ORDER BY sequence, lecture_id",
                (course_id,),
            ).fetchall()
        return [_dict(row) for row in rows]

    def read_import_status(self, import_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM import_statuses WHERE import_id = ?", (import_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"import status not found: {import_id}")
        return _dict(row)

    def create_import_run(
        self,
        *,
        course_id: str,
        source_url: str,
        source_platform: str = "bilibili",
        status: str = "queued",
        stage: str = "queued",
        total_lectures: int = 0,
        completed_lectures: int = 0,
        failed_lectures: int = 0,
        run_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_status = str(status or "").strip() or "queued"
        if cleaned_status not in IMPORT_RUN_STATUSES:
            allowed = ", ".join(sorted(IMPORT_RUN_STATUSES))
            raise ValueError(f"import run status must be one of: {allowed}")
        timestamp = now or self._utc_now()
        record = ImportRunRecord(
            run_id=run_id or f"lite_import_{uuid4().hex[:12]}",
            course_id=str(course_id or "").strip(),
            source_url=str(source_url or "").strip(),
            source_platform=str(source_platform or "").strip() or "bilibili",
            status=cleaned_status,
            stage=str(stage or "").strip() or cleaned_status,
            total_lectures=max(int(total_lectures or 0), 0),
            completed_lectures=max(int(completed_lectures or 0), 0),
            failed_lectures=max(int(failed_lectures or 0), 0),
            created_at=timestamp,
            updated_at=timestamp,
        ).to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO import_runs
                (run_id, course_id, source_url, source_platform, status, stage, total_lectures,
                 completed_lectures, failed_lectures, created_at, updated_at)
                VALUES (:run_id, :course_id, :source_url, :source_platform, :status, :stage,
                        :total_lectures, :completed_lectures, :failed_lectures, :created_at, :updated_at)
                """,
                record,
            )
        return record

    def update_import_run(
        self,
        run_id: str,
        *,
        status: str = "",
        stage: str = "",
        course_id: str = "",
        total_lectures: int | None = None,
        completed_lectures: int | None = None,
        failed_lectures: int | None = None,
        now: str = "",
    ) -> dict[str, Any]:
        run = self.read_import_run(run_id)
        next_status = str(status or run.get("status") or "queued").strip()
        if next_status not in IMPORT_RUN_STATUSES:
            allowed = ", ".join(sorted(IMPORT_RUN_STATUSES))
            raise ValueError(f"import run status must be one of: {allowed}")
        run.update(
            {
                "course_id": str(course_id or run.get("course_id") or "").strip(),
                "status": next_status,
                "stage": str(stage or run.get("stage") or next_status).strip(),
                "updated_at": now or self._utc_now(),
            }
        )
        if total_lectures is not None:
            run["total_lectures"] = max(int(total_lectures or 0), 0)
        if completed_lectures is not None:
            run["completed_lectures"] = max(int(completed_lectures or 0), 0)
        if failed_lectures is not None:
            run["failed_lectures"] = max(int(failed_lectures or 0), 0)
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE import_runs
                SET course_id = :course_id,
                    status = :status,
                    stage = :stage,
                    total_lectures = :total_lectures,
                    completed_lectures = :completed_lectures,
                    failed_lectures = :failed_lectures,
                    updated_at = :updated_at
                WHERE run_id = :run_id
                """,
                run,
            )
            if result.rowcount == 0:
                raise ValueError(f"import run not found: {run_id}")
        return run

    def read_import_run(self, run_id: str) -> dict[str, Any]:
        cleaned_run_id = str(run_id or "").strip()
        if not cleaned_run_id:
            raise ValueError("run_id is required")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM import_runs WHERE run_id = ?", (cleaned_run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"import run not found: {cleaned_run_id}")
        return _dict(row)

    def list_import_runs(self, *, course_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT * FROM import_runs"
        params: list[Any] = []
        if course_id:
            sql += " WHERE course_id = ?"
            params.append(course_id)
        sql += " ORDER BY updated_at DESC, created_at DESC, run_id"
        if limit > 0:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def append_import_event(
        self,
        run_id: str,
        *,
        stage: str,
        status: str,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
        event_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        self.read_import_run(run_id)
        created_at = now or self._utc_now()
        with self._connect() as conn:
            next_index = int(
                conn.execute(
                    "SELECT COALESCE(MAX(event_index), 0) + 1 FROM import_events WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            event = ImportEventRecord(
                event_id=event_id or f"{run_id}::evt_{next_index:04d}",
                run_id=run_id,
                event_index=next_index,
                stage=str(stage or "").strip(),
                status=str(status or "").strip(),
                event_type=str(event_type or "").strip() or "status",
                message=str(message or "").strip(),
                payload=dict(payload or {}),
                created_at=created_at,
            ).to_dict()
            row = dict(event)
            row["payload_json"] = json.dumps(row.pop("payload"), ensure_ascii=False, sort_keys=True)
            conn.execute(
                """
                INSERT INTO import_events
                (event_id, run_id, event_index, stage, status, event_type, message, payload_json, created_at)
                VALUES (:event_id, :run_id, :event_index, :stage, :status, :event_type, :message, :payload_json, :created_at)
                """,
                row,
            )
            conn.execute("UPDATE import_runs SET updated_at = ? WHERE run_id = ?", (created_at, run_id))
        return event

    def list_import_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM import_events WHERE run_id = ? ORDER BY event_index, created_at, event_id",
                (run_id,),
            ).fetchall()
        return [_decode_import_event(row) for row in rows]

    def record_import_artifact(
        self,
        *,
        run_id: str,
        course_id: str,
        lecture_id: str = "",
        artifact_type: str,
        artifact_ref: str = "",
        status: str = "ready",
        payload: dict[str, Any] | None = None,
        artifact_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        self.read_import_run(run_id)
        created_at = now or self._utc_now()
        seed = f"{run_id}\n{course_id}\n{lecture_id}\n{artifact_type}\n{artifact_ref}"
        record = ImportArtifactRecord(
            artifact_id=artifact_id or f"artifact_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}",
            run_id=run_id,
            course_id=str(course_id or "").strip(),
            lecture_id=str(lecture_id or "").strip(),
            artifact_type=str(artifact_type or "").strip(),
            artifact_ref=str(artifact_ref or "").strip(),
            status=str(status or "").strip() or "ready",
            payload=dict(payload or {}),
            created_at=created_at,
        ).to_dict()
        row = dict(record)
        row["payload_json"] = json.dumps(row.pop("payload"), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO import_artifacts
                (artifact_id, run_id, course_id, lecture_id, artifact_type, artifact_ref, status, payload_json, created_at)
                VALUES (:artifact_id, :run_id, :course_id, :lecture_id, :artifact_type, :artifact_ref,
                        :status, :payload_json, :created_at)
                """,
                row,
            )
        return record

    def list_import_artifacts(
        self,
        *,
        run_id: str = "",
        course_id: str = "",
        lecture_id: str = "",
        artifact_type: str = "",
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM import_artifacts"
        params: list[Any] = []
        filters: list[str] = []
        if run_id:
            filters.append("run_id = ?")
            params.append(run_id)
        if course_id:
            filters.append("course_id = ?")
            params.append(course_id)
        if lecture_id:
            filters.append("lecture_id = ?")
            params.append(lecture_id)
        if artifact_type:
            filters.append("artifact_type = ?")
            params.append(artifact_type)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY created_at, artifact_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_decode_import_artifact(row) for row in rows]

    def backfill_import_run_from_readiness(
        self,
        course_id: str,
        *,
        run_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        existing_runs = self.list_import_runs(course_id=course_id, limit=1)
        if existing_runs:
            return existing_runs[0]

        course = self.read_course(course_id)
        readiness = self.summarize_import_readiness(course_id)
        timestamp = now or self._utc_now()
        lecture_count = int(readiness.get("lecture_count") or 0)
        ready_count = int(readiness.get("ready_lecture_count") or 0)
        missing_count = int(readiness.get("missing_lecture_count") or 0)
        ready = bool(readiness.get("ready"))
        status = "completed" if ready else ("partial" if ready_count > 0 else "failed")
        stage = "ready_gate" if ready else "ready_gate_blocked"
        deterministic_run_id = run_id or f"lite_backfill_{hashlib.sha1(course_id.encode('utf-8')).hexdigest()[:12]}"
        run = self.create_import_run(
            run_id=deterministic_run_id,
            course_id=course_id,
            source_url=str(course.get("source_url") or ""),
            source_platform=str(course.get("source_platform") or "bilibili"),
            status=status,
            stage=stage,
            total_lectures=lecture_count,
            completed_lectures=ready_count,
            failed_lectures=missing_count,
            now=timestamp,
        )
        self.record_import_artifact(
            run_id=str(run["run_id"]),
            course_id=course_id,
            artifact_type="course_skeleton",
            artifact_ref=f"sqlite://courses/{course_id}",
            status="ready",
            payload={"lecture_count": lecture_count, "backfill_source": "readiness"},
            now=timestamp,
        )
        self.append_import_event(
            str(run["run_id"]),
            stage="readiness_backfill",
            status=status,
            event_type="backfill_started",
            message="Import ledger backfilled from existing child-local course data.",
            payload={"course_id": course_id, "lecture_count": lecture_count},
            now=timestamp,
        )
        for lecture in readiness.get("lectures") or []:
            lecture_id = str(lecture.get("lecture_id") or "")
            if int(lecture.get("segment_count") or 0) > 0:
                self.record_import_artifact(
                    run_id=str(run["run_id"]),
                    course_id=course_id,
                    lecture_id=lecture_id,
                    artifact_type="transcript",
                    artifact_ref=f"sqlite://transcript_segments/{lecture_id}",
                    status="ready",
                    payload={"segment_count": int(lecture.get("segment_count") or 0)},
                    now=timestamp,
                )
            if int(lecture.get("note_count") or 0) > 0:
                self.record_import_artifact(
                    run_id=str(run["run_id"]),
                    course_id=course_id,
                    lecture_id=lecture_id,
                    artifact_type="lesson_note",
                    artifact_ref=f"sqlite://notes/{course_id}/{lecture_id}",
                    status="ready",
                    payload={"note_count": int(lecture.get("note_count") or 0)},
                    now=timestamp,
                )
            if int(lecture.get("atom_count") or 0) > 0:
                self.record_import_artifact(
                    run_id=str(run["run_id"]),
                    course_id=course_id,
                    lecture_id=lecture_id,
                    artifact_type="knowledge_atoms",
                    artifact_ref=f"sqlite://knowledge_cards/{course_id}/{lecture_id}",
                    status="ready",
                    payload={"atom_count": int(lecture.get("atom_count") or 0)},
                    now=timestamp,
                )
            if int(lecture.get("gate_count") or 0) > 0:
                self.record_import_artifact(
                    run_id=str(run["run_id"]),
                    course_id=course_id,
                    lecture_id=lecture_id,
                    artifact_type="review_gates",
                    artifact_ref=f"sqlite://knowledge_cards/{course_id}/{lecture_id}#review_questions",
                    status="ready",
                    payload={"gate_count": int(lecture.get("gate_count") or 0)},
                    now=timestamp,
                )
            lecture_ready = bool(lecture.get("ready"))
            if lecture_ready:
                self.append_import_event(
                    str(run["run_id"]),
                    stage="lecture_compile",
                    status="completed",
                    event_type="lecture_completed",
                    message=f"Lecture {lecture.get('sequence')} already has transcript, note, atoms, and gates.",
                    payload={
                        "lecture_id": lecture_id,
                        "segment_count": int(lecture.get("segment_count") or 0),
                        "atom_count": int(lecture.get("atom_count") or 0),
                        "gate_count": int(lecture.get("gate_count") or 0),
                    },
                    now=timestamp,
                )
            else:
                missing = list(lecture.get("missing") or [])
                self.record_import_artifact(
                    run_id=str(run["run_id"]),
                    course_id=course_id,
                    lecture_id=lecture_id,
                    artifact_type="lecture_failure",
                    artifact_ref="",
                    status="failed",
                    payload={"missing": missing},
                    now=timestamp,
                )
                self.append_import_event(
                    str(run["run_id"]),
                    stage="lecture_compile",
                    status="failed",
                    event_type="lecture_not_ready",
                    message=f"Lecture {lecture.get('sequence')} is not ready.",
                    payload={"lecture_id": lecture_id, "missing": missing},
                    now=timestamp,
                )
        self.record_import_artifact(
            run_id=str(run["run_id"]),
            course_id=course_id,
            artifact_type="knowledge_atoms",
            artifact_ref=f"sqlite://knowledge_cards/{course_id}",
            status="ready" if int(readiness.get("total_atom_count") or 0) > 0 else "empty",
            payload={
                "atom_count": int(readiness.get("total_atom_count") or 0),
                "gate_count": int(readiness.get("total_gate_count") or 0),
            },
            now=timestamp,
        )
        self.append_import_event(
            str(run["run_id"]),
            stage=stage,
            status=status,
            event_type="ready_gate",
            message="Course ready gate evaluated from existing child-local data.",
            payload={
                "ready": ready,
                "ready_lecture_count": ready_count,
                "lecture_count": lecture_count,
                "missing_lecture_count": missing_count,
            },
            now=timestamp,
        )
        return run

    def backfill_visual_keyframe_status(
        self,
        course_id: str,
        *,
        run_id: str = "",
        unavailable_reason: str = "missing_source_media",
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_course_id = str(course_id or "").strip()
        if not cleaned_course_id:
            raise ValueError("course_id is required")
        self.read_course(cleaned_course_id)
        if run_id:
            run = self.read_import_run(run_id)
            run_course_id = str(run.get("course_id") or "").strip()
            if run_course_id and run_course_id != cleaned_course_id:
                raise ValueError(f"import run does not belong to course: {run_id}")
        else:
            runs = self.list_import_runs(course_id=cleaned_course_id, limit=1)
            run = runs[0] if runs else self.backfill_import_run_from_readiness(cleaned_course_id, now=now)

        timestamp = now or self._utc_now()
        cleaned_run_id = str(run["run_id"])
        lectures = self.read_lectures(cleaned_course_id)
        lecture_statuses: list[dict[str, Any]] = []
        ready_count = 0
        unavailable_count = 0
        for lecture in lectures:
            lecture_id = str(lecture.get("lecture_id") or "").strip()
            visuals = self.list_visual_evidence(course_id=cleaned_course_id, lecture_id=lecture_id)
            generated = [
                item
                for item in visuals
                if "generated_keyframe" in str(item.get("provenance") or "")
            ]
            demo_visual_count = len(visuals) - len(generated)
            if generated:
                status = "ready"
                artifact_ref = f"sqlite://visual_evidence/{cleaned_course_id}/{lecture_id}"
                payload = {
                    "visual_count": len(generated),
                    "visual_ids": [str(item.get("visual_id") or "") for item in generated],
                    "image_paths": [str(item.get("image_path") or "") for item in generated],
                    "provenance": "generated_keyframe",
                    "backfill_source": "visual_evidence",
                }
                ready_count += 1
            else:
                status = "unavailable"
                artifact_ref = ""
                payload = {
                    "reason": str(unavailable_reason or "").strip() or "missing_source_media",
                    "message": "No generated_keyframe visual evidence exists for this lecture.",
                    "demo_visual_count": demo_visual_count,
                    "source_url": str(lecture.get("source_url") or ""),
                    "backfill_source": "visual_evidence",
                }
                unavailable_count += 1
            artifact_id = "artifact_visual_keyframes_" + hashlib.sha1(
                f"{cleaned_run_id}\n{cleaned_course_id}\n{lecture_id}".encode("utf-8")
            ).hexdigest()[:12]
            artifact = self.record_import_artifact(
                run_id=cleaned_run_id,
                course_id=cleaned_course_id,
                lecture_id=lecture_id,
                artifact_type="visual_keyframes",
                artifact_ref=artifact_ref,
                status=status,
                payload=payload,
                artifact_id=artifact_id,
                now=timestamp,
            )
            lecture_statuses.append(
                {
                    "lecture_id": lecture_id,
                    "sequence": lecture.get("sequence"),
                    "title": str(lecture.get("title") or ""),
                    "status": status,
                    "visual_count": len(generated),
                    "demo_visual_count": demo_visual_count,
                    "artifact_id": artifact["artifact_id"],
                    "artifact_ref": artifact_ref,
                    "reason": payload.get("reason", ""),
                }
            )

        return {
            "status": "completed" if unavailable_count == 0 else "partial",
            "course_id": cleaned_course_id,
            "run_id": cleaned_run_id,
            "lecture_count": len(lectures),
            "ready_visual_keyframe_lecture_count": ready_count,
            "unavailable_visual_keyframe_lecture_count": unavailable_count,
            "lectures": lecture_statuses,
        }

    def list_courses(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    courses.*,
                    COALESCE(web_course_bindings.binding_status, 'unbound') AS web_hermes_binding_status,
                    COUNT(DISTINCT lectures.lecture_id) AS lecture_count,
                    COUNT(DISTINCT transcript_segments.lecture_id) AS lecture_transcript_count
                FROM courses
                LEFT JOIN lectures ON lectures.course_id = courses.course_id
                LEFT JOIN transcript_segments ON transcript_segments.course_id = courses.course_id
                LEFT JOIN web_course_bindings ON web_course_bindings.child_course_id = courses.course_id
                GROUP BY courses.course_id
                ORDER BY courses.created_at, courses.course_id
                """
            ).fetchall()
        return [_dict(row) for row in rows]

    def delete_course(self, course_id: str) -> dict[str, Any]:
        cleaned_course_id = str(course_id or "").strip()
        if not cleaned_course_id:
            raise ValueError("course_id is required")
        with self._connect() as conn:
            result = conn.execute("DELETE FROM courses WHERE course_id = ?", (cleaned_course_id,))
        return {"deleted": result.rowcount > 0, "course_id": cleaned_course_id}

    def merge_course_from_store(self, source_store: "SQLiteCourseStore", course_id: str) -> dict[str, Any]:
        cleaned_course_id = str(course_id or "").strip()
        if not cleaned_course_id:
            raise ValueError("course_id is required")
        source_db = Path(source_store.db_path)
        if not source_db.exists():
            raise FileNotFoundError(f"source SQLite database not found: {source_db}")
        source_store.read_course(cleaned_course_id)
        source_db_ref = str(source_db.resolve()).replace("'", "''")
        course_scoped_tables = [
            "courses",
            "lectures",
            "import_statuses",
            "transcript_segments",
            "knowledge_cards",
            "visual_evidence",
            "notes",
            "bookmarks",
            "reading_progress",
            "web_course_bindings",
        ]
        copied: dict[str, int] = {}
        with self._connect() as conn:
            conn.execute(f"ATTACH DATABASE '{source_db_ref}' AS source_store")
            source_run_rows = conn.execute(
                "SELECT run_id FROM source_store.import_runs WHERE course_id = ? ORDER BY created_at, run_id",
                (cleaned_course_id,),
            ).fetchall()
            run_ids = [str(row["run_id"] or "") for row in source_run_rows if str(row["run_id"] or "").strip()]
            conn.execute("DELETE FROM courses WHERE course_id = ?", (cleaned_course_id,))
            for table in course_scoped_tables:
                columns = _table_columns(conn, table)
                column_sql = ", ".join(columns)
                conn.execute(
                    f"""
                    INSERT INTO {table} ({column_sql})
                    SELECT {column_sql} FROM source_store.{table}
                    WHERE {"child_course_id" if table == "web_course_bindings" else "course_id"} = ?
                    """,
                    (cleaned_course_id,),
                )
                copied[table] = int(conn.execute("SELECT changes()").fetchone()[0])
            for run_id in run_ids:
                conn.execute("DELETE FROM import_runs WHERE run_id = ?", (run_id,))
            if run_ids:
                placeholders = ", ".join("?" for _ in run_ids)
                for table in ("import_runs", "import_events", "import_artifacts"):
                    columns = _table_columns(conn, table)
                    column_sql = ", ".join(columns)
                    conn.execute(
                        f"""
                        INSERT INTO {table} ({column_sql})
                        SELECT {column_sql} FROM source_store.{table}
                        WHERE run_id IN ({placeholders})
                        """,
                        run_ids,
                    )
                    copied[table] = int(conn.execute("SELECT changes()").fetchone()[0])
            else:
                copied["import_runs"] = 0
                copied["import_events"] = 0
                copied["import_artifacts"] = 0
        return {"course_id": cleaned_course_id, "copied": copied, "source_database": str(source_db)}

    def upsert_web_course_binding(
        self,
        child_course_id: str,
        *,
        binding_status: str,
        mother_course_id: str = "",
        mother_node_scope: str = "",
        note: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        self.read_course(child_course_id)
        cleaned_status = str(binding_status or "").strip()
        if cleaned_status not in WEB_COURSE_BINDING_STATUSES:
            allowed = ", ".join(sorted(WEB_COURSE_BINDING_STATUSES))
            raise ValueError(f"web course binding status must be one of: {allowed}")
        if cleaned_status == "bound" and not str(mother_course_id or "").strip():
            raise ValueError("mother_course_id is required for a bound Web course")
        timestamp = now or self._utc_now()
        existing = self.get_web_course_binding(child_course_id)
        record = WebCourseBindingRecord(
            child_course_id=str(child_course_id or "").strip(),
            binding_status=cleaned_status,
            mother_course_id=str(mother_course_id or "").strip() if cleaned_status == "bound" else "",
            mother_node_scope=str(mother_node_scope or "").strip() if cleaned_status == "bound" else "",
            note=str(note or "").strip(),
            created_at=str(existing.get("created_at") or timestamp),
            updated_at=timestamp,
        ).to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO web_course_bindings
                (child_course_id, binding_status, mother_course_id, mother_node_scope, note, created_at, updated_at)
                VALUES (:child_course_id, :binding_status, :mother_course_id, :mother_node_scope, :note, :created_at, :updated_at)
                ON CONFLICT(child_course_id) DO UPDATE SET
                    binding_status = excluded.binding_status,
                    mother_course_id = excluded.mother_course_id,
                    mother_node_scope = excluded.mother_node_scope,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                record,
            )
        return record

    def get_web_course_binding(self, child_course_id: str) -> dict[str, Any]:
        cleaned_course_id = str(child_course_id or "").strip()
        if not cleaned_course_id:
            raise ValueError("child_course_id is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM web_course_bindings WHERE child_course_id = ?",
                (cleaned_course_id,),
            ).fetchone()
        return _dict(row)

    def write_transcript_segments(
        self,
        course_id: str,
        lecture_id: str,
        segments: list[TranscriptSegmentRecord],
    ) -> str:
        self._ensure_course_stub(course_id)
        self._ensure_lecture_stub(course_id, lecture_id)
        payload = [segment.to_dict() for segment in segments]
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM transcript_segments WHERE course_id = ? AND lecture_id = ?",
                (course_id, lecture_id),
            )
            conn.executemany(
                """
                INSERT INTO transcript_segments
                (segment_id, course_id, lecture_id, start_seconds, end_seconds, text)
                VALUES (:segment_id, :course_id, :lecture_id, :start_seconds, :end_seconds, :text)
                """,
                [{**item, "course_id": course_id} for item in payload],
            )
        return f"{self.db_path}::transcript_segments/{lecture_id}"

    def read_transcript_segments(self, course_id: str, lecture_id: str) -> list[dict[str, Any]]:
        segments = self.read_transcript_segments_if_exists(course_id, lecture_id)
        if not segments:
            raise FileNotFoundError(f"transcript segments not found: {lecture_id}")
        return segments

    def read_transcript_segments_if_exists(self, course_id: str, lecture_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT segment_id, lecture_id, start_seconds, end_seconds, text
                FROM transcript_segments
                WHERE course_id = ? AND lecture_id = ?
                ORDER BY start_seconds, segment_id
                """,
                (course_id, lecture_id),
            ).fetchall()
        return [_dict(row) for row in rows]

    def read_all_transcript_segments(self, course_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            str(lecture.get("lecture_id", "") or ""): self.read_transcript_segments_if_exists(
                course_id,
                str(lecture.get("lecture_id", "") or ""),
            )
            for lecture in self.read_lectures(course_id)
        }

    def summarize_transcript_coverage(self, course_id: str) -> dict[str, Any]:
        course = self.read_course(course_id)
        lectures = self.read_lectures(course_id)
        lecture_summaries: list[dict[str, Any]] = []
        covered_count = 0
        total_segments = 0
        for lecture in lectures:
            lecture_id = str(lecture.get("lecture_id", "") or "")
            segments = self.read_transcript_segments_if_exists(course_id, lecture_id)
            segment_count = len(segments)
            has_transcript = segment_count > 0
            if has_transcript:
                covered_count += 1
            total_segments += segment_count
            lecture_summaries.append(
                {
                    "lecture_id": lecture_id,
                    "sequence": lecture.get("sequence"),
                    "title": str(lecture.get("title", "") or ""),
                    "source_id": str(lecture.get("source_id", "") or ""),
                    "source_url": str(lecture.get("source_url", "") or ""),
                    "has_transcript": has_transcript,
                    "segment_count": segment_count,
                }
            )
        lecture_count = len(lectures)
        return {
            "course": dict(course),
            "course_id": course_id,
            "lecture_count": lecture_count,
            "covered_lecture_count": covered_count,
            "missing_lecture_count": max(lecture_count - covered_count, 0),
            "total_segment_count": total_segments,
            "coverage_ratio": round(covered_count / lecture_count, 4) if lecture_count else 0.0,
            "lectures": lecture_summaries,
        }

    def summarize_import_readiness(self, course_id: str) -> dict[str, Any]:
        course = self.read_course(course_id)
        lectures = self.read_lectures(course_id)
        cards_by_lecture: dict[str, list[dict[str, Any]]] = {}
        notes_by_lecture: dict[str, list[dict[str, Any]]] = {}
        for card in self.list_knowledge_cards(course_id=course_id):
            cards_by_lecture.setdefault(str(card.get("lecture_id") or ""), []).append(card)
        for note in self.list_notes(course_id=course_id):
            notes_by_lecture.setdefault(str(note.get("lecture_id") or ""), []).append(note)

        lecture_statuses: list[dict[str, Any]] = []
        ready_count = 0
        transcript_ready_count = 0
        note_ready_count = 0
        atom_ready_count = 0
        gate_ready_count = 0
        total_segments = 0
        total_atoms = 0
        total_gates = 0
        for lecture in lectures:
            lecture_id = str(lecture.get("lecture_id") or "")
            segments = self.read_transcript_segments_if_exists(course_id, lecture_id)
            cards = cards_by_lecture.get(lecture_id, [])
            notes = notes_by_lecture.get(lecture_id, [])
            quality_reports = [lite_atom_quality(card) for card in cards]
            quality_pass_count = sum(1 for item in quality_reports if item.get("passed"))
            low_quality_count = max(len(cards) - quality_pass_count, 0)
            gate_count = sum(len(card.get("review_questions") or []) for card in cards)
            has_transcript = bool(segments)
            has_note = bool(notes)
            has_atoms = quality_pass_count > 0
            has_gates = gate_count > 0
            is_ready = has_transcript and has_note and has_atoms and has_gates
            ready_count += int(is_ready)
            transcript_ready_count += int(has_transcript)
            note_ready_count += int(has_note)
            atom_ready_count += int(has_atoms)
            gate_ready_count += int(has_gates)
            total_segments += len(segments)
            total_atoms += quality_pass_count
            total_gates += gate_count
            missing = []
            if not has_transcript:
                missing.append("transcript")
            if not has_note:
                missing.append("lesson_note")
            if not has_atoms:
                missing.append("knowledge_atoms")
            if cards and low_quality_count:
                missing.append("atom_quality")
            if not has_gates:
                missing.append("gates")
            lecture_statuses.append(
                {
                    "lecture_id": lecture_id,
                    "sequence": lecture.get("sequence"),
                    "title": str(lecture.get("title") or ""),
                    "source_url": str(lecture.get("source_url") or ""),
                    "source_id": str(lecture.get("source_id") or ""),
                    "ready": is_ready,
                    "status": "ready" if is_ready else "not_ready",
                    "missing": missing,
                    "segment_count": len(segments),
                    "note_count": len(notes),
                    "atom_count": len(cards),
                    "quality_atom_count": quality_pass_count,
                    "low_quality_atom_count": low_quality_count,
                    "gate_count": gate_count,
                }
            )
        lecture_count = len(lectures)
        is_ready = lecture_count > 0 and ready_count == lecture_count
        latest_run = self.list_import_runs(course_id=course_id, limit=1)
        return {
            "course": course,
            "course_id": course_id,
            "status": "ready" if is_ready else "not_ready",
            "ready": is_ready,
            "lecture_count": lecture_count,
            "ready_lecture_count": ready_count,
            "missing_lecture_count": max(lecture_count - ready_count, 0),
            "transcript_ready_count": transcript_ready_count,
            "note_ready_count": note_ready_count,
            "atom_ready_count": atom_ready_count,
            "gate_ready_count": gate_ready_count,
            "total_segment_count": total_segments,
            "total_atom_count": total_atoms,
            "total_raw_atom_count": sum(len(items) for items in cards_by_lecture.values()),
            "total_gate_count": total_gates,
            "readiness_ratio": round(ready_count / lecture_count, 4) if lecture_count else 0.0,
            "latest_run": latest_run[0] if latest_run else {},
            "lectures": lecture_statuses,
        }

    def read_lecture_reader(
        self,
        course_id: str,
        *,
        lecture_sequence: int | str | None = None,
        lecture_id: str = "",
    ) -> dict[str, Any]:
        course = self.read_course(course_id)
        lecture = self._select_lecture(course_id, lecture_sequence=lecture_sequence, lecture_id=lecture_id)
        segments = self.read_transcript_segments_if_exists(course_id, str(lecture["lecture_id"]))
        return build_lecture_reader_payload(course=course, lecture=lecture, segments=segments)

    def search_transcripts(self, course_id: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        lectures = self.read_lectures(course_id)
        return search_transcript_segments(
            course_id=course_id,
            lectures=lectures,
            segments_by_lecture_id={
                str(lecture.get("lecture_id", "") or ""): self.read_transcript_segments_if_exists(
                    course_id,
                    str(lecture.get("lecture_id", "") or ""),
                )
                for lecture in lectures
            },
            query=query,
            limit=limit,
        )

    def generate_knowledge_cards(
        self,
        course_id: str,
        *,
        lecture_id: str = "",
        overwrite: bool = True,
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
        course = self.read_course(course_id)
        selected_lecture_id = str(lecture_id or "").strip()
        lectures = self.read_lectures(course_id)
        if selected_lecture_id:
            lectures = [lecture for lecture in lectures if str(lecture.get("lecture_id") or "") == selected_lecture_id]
            if not lectures:
                raise ValueError(f"lecture not found: {selected_lecture_id}")
        generated_cards: list[dict[str, Any]] = []
        for lecture in lectures:
            current_lecture_id = str(lecture.get("lecture_id") or "")
            segments = self.read_transcript_segments_if_exists(course_id, current_lecture_id)
            lecture_cards = [
                card.to_dict()
                for card in self._build_lecture_knowledge_cards(
                    course_id=course_id,
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
            ]
            if str(compile_mode or "").strip() == "model" and segments and not lecture_cards:
                raise RuntimeError(
                    f"model lecture dossier generated zero knowledge cards for {current_lecture_id}"
                )
            generated_cards.extend(lecture_cards)
        if overwrite:
            cards = [
                card
                for card in self.list_knowledge_cards(course_id=course_id)
                if not _is_generated_card(card)
                or (selected_lecture_id and str(card.get("lecture_id") or "") != selected_lecture_id)
            ]
            existing_ids = {str(card.get("card_id") or "") for card in cards}
            cards.extend(card for card in generated_cards if str(card.get("card_id") or "") not in existing_ids)
        else:
            cards = self.list_knowledge_cards(course_id=course_id)
            existing_ids = {str(card.get("card_id") or "") for card in cards}
            cards.extend(card for card in generated_cards if str(card.get("card_id") or "") not in existing_ids)
        cards.sort(key=lambda card: (str(card.get("lecture_id") or ""), str(card.get("card_id") or "")))
        self._replace_knowledge_cards(course_id, cards)
        return {
            "course_id": course_id,
            "card_count": len(cards),
            "generated_card_count": len(generated_cards),
            "cards": cards,
            "path": f"{self.db_path}::knowledge_cards/{course_id}",
        }

    def upsert_lecture_knowledge_cards_from_dossier(
        self,
        course_id: str,
        *,
        lecture: dict[str, Any],
        segments: list[dict[str, Any]],
        dossier: Any,
        overwrite: bool = True,
    ) -> dict[str, Any]:
        selected_lecture_id = str(lecture.get("lecture_id") or "").strip()
        if not selected_lecture_id:
            raise ValueError("lecture.lecture_id is required")
        generated_cards = [
            card.to_dict()
            for card in self._build_lecture_knowledge_cards_from_dossier(
                course_id=course_id,
                lecture=lecture,
                segments=segments,
                dossier=dossier,
            )
        ]
        if str((dossier.to_dict() if hasattr(dossier, "to_dict") else dossier).get("compile_source") or "") == "model_map_reduce" and segments and not generated_cards:
            raise RuntimeError(
                f"model lecture dossier generated zero knowledge cards for {selected_lecture_id}"
            )
        if overwrite:
            cards = [
                card
                for card in self.list_knowledge_cards(course_id=course_id)
                if not _is_generated_card(card)
                or str(card.get("lecture_id") or "") != selected_lecture_id
            ]
            existing_ids = {str(card.get("card_id") or "") for card in cards}
            cards.extend(card for card in generated_cards if str(card.get("card_id") or "") not in existing_ids)
        else:
            cards = self.list_knowledge_cards(course_id=course_id)
            existing_ids = {str(card.get("card_id") or "") for card in cards}
            cards.extend(card for card in generated_cards if str(card.get("card_id") or "") not in existing_ids)
        cards.sort(key=lambda card: (str(card.get("lecture_id") or ""), str(card.get("card_id") or "")))
        if overwrite:
            lecture_cards = [
                card
                for card in cards
                if str(card.get("lecture_id") or "") == selected_lecture_id
            ]
            self._replace_knowledge_cards_for_lecture(course_id, selected_lecture_id, lecture_cards)
            final_cards = self.list_knowledge_cards(course_id=course_id)
        else:
            self._replace_knowledge_cards(course_id, cards)
            final_cards = cards
        return {
            "course_id": course_id,
            "lecture_id": selected_lecture_id,
            "card_count": len(final_cards),
            "generated_card_count": len(generated_cards),
            "cards": final_cards,
            "path": f"{self.db_path}::knowledge_cards/{course_id}/{selected_lecture_id}",
        }

    def list_knowledge_cards(self, *, course_id: str, lecture_id: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM knowledge_cards WHERE course_id = ?"
        params: list[Any] = [course_id]
        if lecture_id:
            query += " AND lecture_id = ?"
            params.append(lecture_id)
        query += " ORDER BY lecture_id, card_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_decode_card(row) for row in rows]

    def read_knowledge_card(self, course_id: str, card_id: str) -> dict[str, Any]:
        cleaned_card_id = str(card_id or "").strip()
        if not cleaned_card_id:
            raise ValueError("card_id is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM knowledge_cards WHERE course_id = ? AND card_id = ?",
                (course_id, cleaned_card_id),
            ).fetchone()
        if row is None:
            raise ValueError(f"card not found: {cleaned_card_id}")
        return _decode_card(row)

    def write_visual_evidence_records(
        self,
        course_id: str,
        records: list[VisualEvidenceRecord | dict[str, Any]],
    ) -> str:
        self.read_course(course_id)
        normalized = [self._normalize_visual_evidence(course_id, record) for record in records]
        normalized.sort(key=lambda item: (str(item.get("lecture_id") or ""), str(item.get("visual_id") or "")))
        with self._connect() as conn:
            conn.execute("DELETE FROM visual_evidence WHERE course_id = ?", (course_id,))
            conn.executemany(
                """
                INSERT INTO visual_evidence
                (visual_id, course_id, lecture_id, segment_id, card_id, title, explanation,
                 image_path, source_url, provenance, created_at)
                VALUES (:visual_id, :course_id, :lecture_id, :segment_id, :card_id, :title, :explanation,
                        :image_path, :source_url, :provenance, :created_at)
                """,
                normalized,
            )
        return f"{self.db_path}::visual_evidence/{course_id}"

    def upsert_visual_evidence_records(
        self,
        course_id: str,
        records: list[VisualEvidenceRecord | dict[str, Any]],
    ) -> str:
        self.read_course(course_id)
        normalized = [self._normalize_visual_evidence(course_id, record) for record in records]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO visual_evidence
                (visual_id, course_id, lecture_id, segment_id, card_id, title, explanation,
                 image_path, source_url, provenance, created_at)
                VALUES (:visual_id, :course_id, :lecture_id, :segment_id, :card_id, :title, :explanation,
                        :image_path, :source_url, :provenance, :created_at)
                """,
                normalized,
            )
        return f"{self.db_path}::visual_evidence/{course_id}"

    def list_visual_evidence(
        self,
        *,
        course_id: str,
        lecture_id: str = "",
        query: str = "",
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM visual_evidence WHERE course_id = ?"
        params: list[Any] = [course_id]
        if lecture_id:
            sql += " AND lecture_id = ?"
            params.append(lecture_id)
        sql += " ORDER BY lecture_id, visual_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        items = [_dict(row) for row in rows]
        cleaned_query = str(query or "").strip().lower()
        if cleaned_query:
            query_terms = _query_terms(cleaned_query)
            items = [
                item
                for item in items
                if _visual_search_matches(item, cleaned_query=cleaned_query, query_terms=query_terms)
            ]
        return items

    def read_visual_evidence(self, course_id: str, visual_id: str) -> dict[str, Any]:
        cleaned_visual_id = str(visual_id or "").strip()
        if not cleaned_visual_id:
            raise ValueError("visual_id is required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM visual_evidence WHERE course_id = ? AND visual_id = ?",
                (course_id, cleaned_visual_id),
            ).fetchone()
        if row is None:
            raise ValueError(f"visual evidence not found: {cleaned_visual_id}")
        return _dict(row)

    def select_visual_evidence(
        self,
        *,
        course_id: str,
        visual_id: str = "",
        lecture_id: str = "",
        query: str = "",
    ) -> dict[str, Any]:
        if visual_id:
            return self.read_visual_evidence(course_id, visual_id)
        candidates = self.list_visual_evidence(course_id=course_id, lecture_id=lecture_id, query=query)
        if not candidates:
            raise ValueError("No visual evidence matched the request")
        return dict(candidates[0])

    def create_note(
        self,
        course_id: str,
        lecture_id: str,
        body: str,
        *,
        note_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        self._ensure_lecture_exists(course_id, lecture_id)
        cleaned_body = str(body or "").strip()
        if not cleaned_body:
            raise ValueError("note body is required")
        created_at = now or self._utc_now()
        note = NoteRecord(
            note_id=note_id or f"note_{uuid4().hex[:12]}",
            course_id=course_id,
            lecture_id=lecture_id,
            body=cleaned_body,
            created_at=created_at,
            updated_at=created_at,
        ).to_dict()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO notes (note_id, course_id, lecture_id, body, created_at, updated_at)
                    VALUES (:note_id, :course_id, :lecture_id, :body, :created_at, :updated_at)
                    """,
                    note,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"note_id already exists: {note['note_id']}") from exc
        return note

    def list_notes(self, *, course_id: str, lecture_id: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM notes WHERE course_id = ?"
        params: list[Any] = [course_id]
        if lecture_id:
            sql += " AND lecture_id = ?"
            params.append(lecture_id)
        sql += " ORDER BY created_at, note_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def update_note(
        self,
        course_id: str,
        note_id: str,
        body: str,
        *,
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_note_id = str(note_id or "").strip()
        cleaned_body = str(body or "").strip()
        if not cleaned_note_id:
            raise ValueError("note_id is required")
        if not cleaned_body:
            raise ValueError("note body is required")
        updated_at = now or self._utc_now()
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE notes SET body = ?, updated_at = ? WHERE course_id = ? AND note_id = ?",
                (cleaned_body, updated_at, course_id, cleaned_note_id),
            )
            if result.rowcount == 0:
                raise ValueError(f"note not found: {cleaned_note_id}")
            row = conn.execute(
                "SELECT * FROM notes WHERE course_id = ? AND note_id = ?",
                (course_id, cleaned_note_id),
            ).fetchone()
        return _dict(row)

    def delete_note(self, course_id: str, note_id: str) -> dict[str, Any]:
        cleaned_note_id = str(note_id or "").strip()
        if not cleaned_note_id:
            raise ValueError("note_id is required")
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM notes WHERE course_id = ? AND note_id = ?",
                (course_id, cleaned_note_id),
            )
        return {"deleted": result.rowcount > 0, "note_id": cleaned_note_id}

    def create_bookmark(
        self,
        course_id: str,
        target_type: str,
        target_id: str,
        *,
        bookmark_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_type = str(target_type or "").strip()
        cleaned_target = str(target_id or "").strip()
        if cleaned_type not in {"lecture", "segment", "card"}:
            raise ValueError("target_type must be one of: lecture, segment, card")
        if not cleaned_target:
            raise ValueError("target_id is required")
        self._ensure_bookmark_target_exists(course_id, cleaned_type, cleaned_target)
        bookmark = BookmarkRecord(
            bookmark_id=bookmark_id or f"bookmark_{uuid4().hex[:12]}",
            target_type=cleaned_type,
            target_id=cleaned_target,
            created_at=now or self._utc_now(),
        ).to_dict()
        bookmark["course_id"] = course_id
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO bookmarks (bookmark_id, course_id, target_type, target_id, created_at)
                    VALUES (:bookmark_id, :course_id, :target_type, :target_id, :created_at)
                    """,
                    bookmark,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"bookmark_id already exists: {bookmark['bookmark_id']}") from exc
        bookmark.pop("course_id", None)
        return bookmark

    def list_bookmarks(self, *, course_id: str, target_type: str = "") -> list[dict[str, Any]]:
        sql = "SELECT bookmark_id, target_type, target_id, created_at FROM bookmarks WHERE course_id = ?"
        params: list[Any] = [course_id]
        if target_type:
            sql += " AND target_type = ?"
            params.append(target_type)
        sql += " ORDER BY created_at, bookmark_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def delete_bookmark(self, course_id: str, bookmark_id: str) -> dict[str, Any]:
        cleaned_bookmark_id = str(bookmark_id or "").strip()
        if not cleaned_bookmark_id:
            raise ValueError("bookmark_id is required")
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM bookmarks WHERE course_id = ? AND bookmark_id = ?",
                (course_id, cleaned_bookmark_id),
            )
        return {"deleted": result.rowcount > 0, "bookmark_id": cleaned_bookmark_id}

    def set_reading_progress(
        self,
        course_id: str,
        lecture_id: str,
        status: str,
        *,
        now: str = "",
    ) -> dict[str, Any]:
        cleaned_status = str(status or "").strip()
        if cleaned_status not in READING_PROGRESS_STATUSES:
            allowed = ", ".join(sorted(READING_PROGRESS_STATUSES))
            raise ValueError(f"status must be one of: {allowed}")
        self._ensure_lecture_exists(course_id, lecture_id)
        record = ReadingProgressRecord(
            course_id=course_id,
            lecture_id=lecture_id,
            status=cleaned_status,
            last_opened_at=now or self._utc_now(),
        ).to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reading_progress (course_id, lecture_id, status, last_opened_at)
                VALUES (:course_id, :lecture_id, :status, :last_opened_at)
                ON CONFLICT(course_id, lecture_id) DO UPDATE SET
                    status = excluded.status,
                    last_opened_at = excluded.last_opened_at
                """,
                record,
            )
            conn.execute(
                "UPDATE lectures SET read_status = ? WHERE course_id = ? AND lecture_id = ?",
                (cleaned_status, course_id, lecture_id),
            )
        return record

    def get_reading_progress(self, course_id: str, lecture_id: str) -> dict[str, Any]:
        self._ensure_lecture_exists(course_id, lecture_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reading_progress WHERE course_id = ? AND lecture_id = ?",
                (course_id, lecture_id),
            ).fetchone()
        if row is None:
            return ReadingProgressRecord(
                course_id=course_id,
                lecture_id=lecture_id,
                status="not_started",
                last_opened_at="",
            ).to_dict()
        return _dict(row)

    def list_reading_progress(self, *, course_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reading_progress WHERE course_id = ? ORDER BY lecture_id",
                (course_id,),
            ).fetchall()
        return [_dict(row) for row in rows]

    def create_chat_thread(
        self,
        course_id: str,
        *,
        title: str = "",
        channel: str = "web",
        thread_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        self.read_course(course_id)
        created_at = now or self._utc_now()
        cleaned_title = str(title or "").strip() or "New chat"
        cleaned_channel = str(channel or "web").strip() or "web"
        thread = ChatThreadRecord(
            thread_id=thread_id or f"chat_thread_{uuid4().hex[:12]}",
            course_id=course_id,
            title=cleaned_title,
            channel=cleaned_channel,
            created_at=created_at,
            updated_at=created_at,
        ).to_dict()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO chat_threads
                    (thread_id, course_id, title, channel, created_at, updated_at)
                    VALUES (:thread_id, :course_id, :title, :channel, :created_at, :updated_at)
                    """,
                    thread,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"chat thread already exists: {thread['thread_id']}") from exc
        return thread

    def read_chat_thread(self, thread_id: str) -> dict[str, Any]:
        cleaned_thread_id = str(thread_id or "").strip()
        if not cleaned_thread_id:
            raise ValueError("thread_id is required")
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM chat_threads WHERE thread_id = ?", (cleaned_thread_id,)).fetchone()
        if row is None:
            raise ValueError(f"chat thread not found: {cleaned_thread_id}")
        return _dict(row)

    def list_chat_threads(self, *, course_id: str = "", channel: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM chat_threads"
        params: list[Any] = []
        filters: list[str] = []
        if course_id:
            filters.append("course_id = ?")
            params.append(course_id)
        if channel:
            filters.append("channel = ?")
            params.append(channel)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY updated_at DESC, created_at DESC, thread_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_dict(row) for row in rows]

    def delete_chat_threads(
        self,
        *,
        course_id: str = "",
        channel: str = "",
        channel_prefix: str = "",
        updated_before: str = "",
    ) -> dict[str, Any]:
        params: list[Any] = []
        filters: list[str] = []
        if course_id:
            filters.append("course_id = ?")
            params.append(course_id)
        if channel:
            filters.append("channel = ?")
            params.append(channel)
        if channel_prefix:
            filters.append("channel LIKE ?")
            params.append(f"{channel_prefix}%")
        if updated_before:
            filters.append("updated_at < ?")
            params.append(updated_before)
        if not filters:
            raise ValueError("delete_chat_threads requires at least one filter")
        where = " AND ".join(filters)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT thread_id FROM chat_threads WHERE {where}", params).fetchall()
            thread_ids = [str(row["thread_id"]) for row in rows]
            if thread_ids:
                placeholders = ",".join("?" for _ in thread_ids)
                conn.execute(f"DELETE FROM chat_threads WHERE thread_id IN ({placeholders})", thread_ids)
        return {
            "deleted_thread_count": len(thread_ids),
            "deleted_thread_ids": thread_ids,
        }

    def append_chat_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        *,
        message_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        thread = self.read_chat_thread(thread_id)
        cleaned_role = str(role or "").strip()
        if cleaned_role not in CHAT_MESSAGE_ROLES:
            allowed = ", ".join(sorted(CHAT_MESSAGE_ROLES))
            raise ValueError(f"chat message role must be one of: {allowed}")
        created_at = now or self._utc_now()
        message = ChatMessageRecord(
            message_id=message_id or f"chat_msg_{uuid4().hex[:12]}",
            thread_id=str(thread["thread_id"]),
            role=cleaned_role,
            content=str(content or ""),
            created_at=created_at,
        ).to_dict()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO chat_messages
                    (message_id, thread_id, role, content, created_at)
                    VALUES (:message_id, :thread_id, :role, :content, :created_at)
                    """,
                    message,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"chat message already exists: {message['message_id']}") from exc
            conn.execute(
                "UPDATE chat_threads SET updated_at = ? WHERE thread_id = ?",
                (created_at, str(thread["thread_id"])),
            )
        return message

    def list_chat_messages(self, thread_id: str) -> list[dict[str, Any]]:
        cleaned_thread_id = str(thread_id or "").strip()
        if not cleaned_thread_id:
            raise ValueError("thread_id is required")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE thread_id = ? ORDER BY created_at, message_id",
                (cleaned_thread_id,),
            ).fetchall()
        return [_dict(row) for row in rows]

    def append_chat_event(
        self,
        thread_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        message_id: str = "",
        tool_name: str = "",
        event_id: str = "",
        now: str = "",
    ) -> dict[str, Any]:
        thread = self.read_chat_thread(thread_id)
        cleaned_event_type = str(event_type or "").strip()
        if cleaned_event_type not in CHAT_EVENT_TYPES:
            allowed = ", ".join(sorted(CHAT_EVENT_TYPES))
            raise ValueError(f"chat event type must be one of: {allowed}")
        cleaned_message_id = str(message_id or "").strip()
        if cleaned_message_id and not any(
            str(message.get("message_id") or "") == cleaned_message_id
            for message in self.list_chat_messages(str(thread["thread_id"]))
        ):
            raise ValueError(f"chat message not found for event: {cleaned_message_id}")
        created_at = now or self._utc_now()
        event = ChatEventRecord(
            event_id=event_id or f"chat_evt_{uuid4().hex[:12]}",
            thread_id=str(thread["thread_id"]),
            message_id=cleaned_message_id,
            event_type=cleaned_event_type,
            tool_name=str(tool_name or "").strip(),
            payload=dict(payload or {}),
            created_at=created_at,
        ).to_dict()
        row = dict(event)
        row["payload_json"] = json.dumps(row.pop("payload"), ensure_ascii=False, sort_keys=True)
        row["message_id"] = row["message_id"] or None
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO chat_events
                    (event_id, thread_id, message_id, event_type, tool_name, payload_json, created_at)
                    VALUES (:event_id, :thread_id, :message_id, :event_type, :tool_name, :payload_json, :created_at)
                    """,
                    row,
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"chat event already exists: {event['event_id']}") from exc
            conn.execute(
                "UPDATE chat_threads SET updated_at = ? WHERE thread_id = ?",
                (created_at, str(thread["thread_id"])),
            )
        return event

    def list_chat_events(self, thread_id: str) -> list[dict[str, Any]]:
        cleaned_thread_id = str(thread_id or "").strip()
        if not cleaned_thread_id:
            raise ValueError("thread_id is required")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_events WHERE thread_id = ? ORDER BY created_at, event_id",
                (cleaned_thread_id,),
            ).fetchall()
        return [_decode_chat_event(row) for row in rows]

    def import_from_json_store(self, json_store: Any) -> dict[str, Any]:
        migrated_courses = 0
        migrated_lectures = 0
        courses_root = Path(json_store.root) / "courses"
        if not courses_root.exists():
            return {"migrated_courses": 0, "migrated_lectures": 0, "database": str(self.db_path)}
        for course_path in sorted(courses_root.glob("*/course.json")):
            course_id = course_path.parent.name
            course = json_store.read_course(course_id)
            lectures = json_store.read_lectures(course_id)
            import_id = f"{course_id}::import"
            import_status = {
                "import_id": import_id,
                "course_id": course_id,
                "source_url": str(course.get("source_url") or ""),
                "source_platform": str(course.get("source_platform") or ""),
                "status": str(course.get("import_status") or "accepted"),
                "stage": "json_migrated",
                "total_lectures": len(lectures),
                "completed_lectures": 0,
                "failed_lectures": 0,
                "created_at": str(course.get("created_at") or self._utc_now()),
                "updated_at": str(course.get("updated_at") or self._utc_now()),
            }
            skeleton = _skeleton_like(course, lectures, import_status)
            self.write_skeleton(skeleton)
            for lecture in lectures:
                lecture_id = str(lecture.get("lecture_id") or "")
                records = [
                    TranscriptSegmentRecord(
                        segment_id=str(segment.get("segment_id") or ""),
                        lecture_id=str(segment.get("lecture_id") or lecture_id),
                        start_seconds=float(segment.get("start_seconds") or 0.0),
                        end_seconds=float(segment.get("end_seconds") or 0.0),
                        text=str(segment.get("text") or ""),
                    )
                    for segment in json_store.read_transcript_segments_if_exists(course_id, lecture_id)
                ]
                if records:
                    self.write_transcript_segments(course_id, lecture_id, records)
            self._replace_knowledge_cards(course_id, json_store.list_knowledge_cards(course_id=course_id))
            visuals = json_store.list_visual_evidence(course_id=course_id)
            if visuals:
                self.write_visual_evidence_records(course_id, visuals)
            for note in json_store.list_notes(course_id=course_id):
                self.create_note(
                    course_id,
                    str(note.get("lecture_id") or ""),
                    str(note.get("body") or ""),
                    note_id=str(note.get("note_id") or ""),
                    now=str(note.get("created_at") or ""),
                )
                if str(note.get("updated_at") or ""):
                    self.update_note(course_id, str(note.get("note_id") or ""), str(note.get("body") or ""), now=str(note.get("updated_at") or ""))
            for progress in json_store.list_reading_progress(course_id=course_id):
                self.set_reading_progress(
                    course_id,
                    str(progress.get("lecture_id") or ""),
                    str(progress.get("status") or "not_started"),
                    now=str(progress.get("last_opened_at") or ""),
                )
            for bookmark in json_store.list_bookmarks(course_id=course_id):
                self.create_bookmark(
                    course_id,
                    str(bookmark.get("target_type") or ""),
                    str(bookmark.get("target_id") or ""),
                    bookmark_id=str(bookmark.get("bookmark_id") or ""),
                    now=str(bookmark.get("created_at") or ""),
                )
            self.backfill_import_run_from_readiness(
                course_id,
                now=str(course.get("updated_at") or course.get("created_at") or ""),
            )
            migrated_courses += 1
            migrated_lectures += len(lectures)
        return {"migrated_courses": migrated_courses, "migrated_lectures": migrated_lectures, "database": str(self.db_path)}

    def _replace_knowledge_cards(self, course_id: str, cards: Iterable[dict[str, Any]]) -> None:
        self._replace_knowledge_cards_for_lecture(course_id, "", cards)

    def _replace_knowledge_cards_for_lecture(
        self,
        course_id: str,
        lecture_id: str,
        cards: Iterable[dict[str, Any]],
    ) -> None:
        rows = []
        for card in cards:
            payload = dict(card)
            payload["course_id"] = str(payload.get("course_id") or course_id)
            payload["source_segment_ids_json"] = json.dumps(list(payload.pop("source_segment_ids", []) or []), ensure_ascii=False)
            payload["tags_json"] = json.dumps(list(payload.pop("tags", []) or []), ensure_ascii=False)
            payload["atom_type"] = str(payload.get("atom_type") or "concept")
            payload["summary"] = str(payload.get("summary") or payload.get("body") or "")
            payload["review_questions_json"] = json.dumps(list(payload.pop("review_questions", []) or []), ensure_ascii=False)
            payload["anchor_refs_json"] = json.dumps(list(payload.pop("anchor_refs", []) or []), ensure_ascii=False)
            payload["confidence"] = float(payload.get("confidence", 0.75) or 0.75)
            payload["status_lite"] = str(payload.get("status_lite") or "locked")
            rows.append(payload)
        with self._connect() as conn:
            if lecture_id:
                conn.execute(
                    "DELETE FROM knowledge_cards WHERE course_id = ? AND lecture_id = ?",
                    (course_id, lecture_id),
                )
            else:
                conn.execute("DELETE FROM knowledge_cards WHERE course_id = ?", (course_id,))
            conn.executemany(
                """
                INSERT INTO knowledge_cards
                (card_id, course_id, lecture_id, title, body, source_segment_ids_json, tags_json, atom_type, summary, review_questions_json, anchor_refs_json, confidence, status_lite)
                VALUES (:card_id, :course_id, :lecture_id, :title, :body, :source_segment_ids_json, :tags_json, :atom_type, :summary, :review_questions_json, :anchor_refs_json, :confidence, :status_lite)
                """,
                rows,
            )

    def _select_lecture(
        self,
        course_id: str,
        *,
        lecture_sequence: int | str | None = None,
        lecture_id: str = "",
    ) -> dict[str, Any]:
        cleaned_lecture_id = str(lecture_id or "").strip()
        parsed_sequence: int | None = None
        if lecture_sequence not in (None, ""):
            try:
                parsed_sequence = int(lecture_sequence)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"lecture_sequence must be an integer: {lecture_sequence}") from exc
        for lecture in self.read_lectures(course_id):
            if cleaned_lecture_id and str(lecture.get("lecture_id", "") or "") == cleaned_lecture_id:
                return lecture
            if parsed_sequence is not None and int(lecture.get("sequence", 0) or 0) == parsed_sequence:
                return lecture
        selector = f"lecture_id={cleaned_lecture_id}" if cleaned_lecture_id else f"lecture_sequence={parsed_sequence}"
        raise ValueError(f"No lecture matched {selector}")

    def _ensure_lecture_exists(self, course_id: str, lecture_id: str) -> dict[str, Any]:
        cleaned_lecture_id = str(lecture_id or "").strip()
        if not cleaned_lecture_id:
            raise ValueError("lecture_id is required")
        return self._select_lecture(course_id, lecture_id=cleaned_lecture_id)

    def _ensure_course_stub(self, course_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO courses
                (course_id, title, source_url, source_platform, import_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    course_id,
                    course_id,
                    "",
                    "",
                    "accepted",
                    self._utc_now(),
                    self._utc_now(),
                ),
            )

    def _ensure_lecture_stub(self, course_id: str, lecture_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO lectures
                (lecture_id, course_id, title, source_url, source_id, sequence, duration_seconds, read_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (lecture_id, course_id, lecture_id, "", "", 0, None, "not_started"),
            )

    def _ensure_bookmark_target_exists(self, course_id: str, target_type: str, target_id: str) -> None:
        if target_type == "lecture":
            self._ensure_lecture_exists(course_id, target_id)
            return
        if target_type == "segment":
            for segments in self.read_all_transcript_segments(course_id).values():
                if any(str(segment.get("segment_id") or "") == target_id for segment in segments):
                    return
            raise ValueError(f"segment not found: {target_id}")
        if target_type == "card":
            self.read_knowledge_card(course_id, target_id)
            return

    def _normalize_visual_evidence(
        self,
        course_id: str,
        record: VisualEvidenceRecord | dict[str, Any],
    ) -> dict[str, Any]:
        payload = record.to_dict() if isinstance(record, VisualEvidenceRecord) else dict(record)
        payload["course_id"] = str(payload.get("course_id") or course_id).strip()
        if payload["course_id"] != course_id:
            raise ValueError(f"visual evidence course_id mismatch: {payload['course_id']} != {course_id}")
        visual_id = str(payload.get("visual_id") or "").strip()
        lecture_id = str(payload.get("lecture_id") or "").strip()
        title = str(payload.get("title") or "").strip()
        explanation = str(payload.get("explanation") or "").strip()
        image_path = str(payload.get("image_path") or "").strip().replace("\\", "/")
        provenance = str(payload.get("provenance") or "").strip()
        if not visual_id:
            raise ValueError("visual_id is required")
        if not lecture_id:
            raise ValueError("lecture_id is required")
        if not title:
            raise ValueError("visual evidence title is required")
        if not explanation:
            raise ValueError("visual evidence explanation is required")
        if not image_path:
            raise ValueError("visual evidence image_path is required")
        if Path(image_path).is_absolute() or ".." in Path(image_path).parts:
            raise ValueError("visual evidence image_path must be a repo-local relative path")
        if not provenance:
            raise ValueError("visual evidence provenance is required")
        self._ensure_lecture_exists(course_id, lecture_id)
        segment_id = str(payload.get("segment_id") or "").strip()
        if segment_id:
            segments = self.read_transcript_segments_if_exists(course_id, lecture_id)
            if not any(str(segment.get("segment_id") or "") == segment_id for segment in segments):
                raise ValueError(f"segment not found for visual evidence: {segment_id}")
        card_id = str(payload.get("card_id") or "").strip()
        if card_id:
            self.read_knowledge_card(course_id, card_id)
        return {
            "visual_id": visual_id,
            "course_id": course_id,
            "lecture_id": lecture_id,
            "segment_id": segment_id,
            "card_id": card_id,
            "title": title,
            "explanation": explanation,
            "image_path": image_path,
            "source_url": str(payload.get("source_url") or "").strip(),
            "provenance": provenance,
            "created_at": str(payload.get("created_at") or self._utc_now()).strip(),
        }

    def _build_knowledge_cards(
        self,
        *,
        course_id: str,
        lecture: dict[str, Any],
        segment: dict[str, Any],
    ) -> list[KnowledgeCardRecord]:
        segment_id = str(segment.get("segment_id") or "").strip()
        if not segment_id:
            raise ValueError("segment_id is required to build a knowledge card")
        text = str(segment.get("text") or "").strip()
        lecture_title = str(lecture.get("title") or "").strip()
        atoms = _knowledge_atom_specs(text, fallback=lecture_title)
        cards: list[KnowledgeCardRecord] = []
        for index, atom in enumerate(atoms, start=1):
            card_seed = f"{segment_id}::{index}::{atom['title']}"
            card_id = f"card_{hashlib.sha1(card_seed.encode('utf-8')).hexdigest()[:12]}"
            cards.append(
                KnowledgeCardRecord(
                    card_id=card_id,
                    course_id=course_id,
                    lecture_id=str(lecture.get("lecture_id") or segment.get("lecture_id") or ""),
                    title=str(atom["title"]),
                    body=str(atom["body"]),
                    source_segment_ids=[segment_id],
                    tags=list(atom["tags"]),
                    atom_type=str(atom["atom_type"]),
                    summary=str(atom["summary"]),
                    review_questions=list(atom["review_questions"]),
                    anchor_refs=list(atom["anchor_refs"]),
                    confidence=float(atom["confidence"]),
                    status_lite=str(atom["status_lite"]),
                )
            )
        return cards

    def _build_lecture_knowledge_cards(
        self,
        *,
        course_id: str,
        course: dict[str, Any] | None = None,
        lecture: dict[str, Any],
        segments: list[dict[str, Any]],
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
    ) -> list[KnowledgeCardRecord]:
        if not segments:
            return []
        lecture_id = str(lecture.get("lecture_id") or "")
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
        return self._build_lecture_knowledge_cards_from_dossier(
            course_id=course_id,
            lecture=lecture,
            segments=segments,
            dossier=dossier,
        )

    def _build_lecture_knowledge_cards_from_dossier(
        self,
        *,
        course_id: str,
        lecture: dict[str, Any],
        segments: list[dict[str, Any]],
        dossier: Any,
    ) -> list[KnowledgeCardRecord]:
        lecture_id = str(lecture.get("lecture_id") or "")
        payload = dossier.to_dict() if hasattr(dossier, "to_dict") else dict(dossier)
        cards: list[KnowledgeCardRecord] = []
        atoms = _card_atoms_from_dossier(payload)
        anchor_segment_ids = _anchor_segment_ids_from_dossier(payload, segments)
        for index, atom in enumerate(atoms, start=1):
            source_segment_ids = [str(item) for item in atom.get("source_segment_ids") or [] if str(item).strip()]
            if not source_segment_ids:
                source_segment_ids = _segment_ids_for_atom(atom, anchor_segment_ids)
            if not source_segment_ids and segments:
                source_segment_ids = [str(segments[min(index - 1, len(segments) - 1)].get("segment_id") or "")]
            card_seed = f"{lecture_id}::{index}::{atom['canonical_title']}"
            card_id = f"card_{hashlib.sha1(card_seed.encode('utf-8')).hexdigest()[:12]}"
            review_questions = [
                str(item).strip()
                for item in atom.get("review_questions") or list(payload.get("review_questions") or [])[:1]
                if str(item).strip()
            ]
            cards.append(
                KnowledgeCardRecord(
                    card_id=card_id,
                    course_id=course_id,
                    lecture_id=lecture_id,
                    title=str(atom["canonical_title"]),
                    body=str(atom["body_markdown"]),
                    source_segment_ids=source_segment_ids,
                    tags=list(atom.get("tags") or []),
                    atom_type=str(atom.get("atom_type") or "concept"),
                    summary=str(atom.get("summary") or ""),
                    review_questions=review_questions,
                    anchor_refs=list(atom.get("anchor_ids") or []),
                    confidence=float(atom.get("confidence") or 0.78),
                    status_lite=str(atom.get("status_lite") or atom.get("status") or "locked"),
                )
            )
        return cards

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        _init_schema(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_platform TEXT NOT NULL,
            import_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lectures (
            lecture_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            title TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            duration_seconds INTEGER,
            read_status TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_lectures_course_sequence ON lectures(course_id, sequence);
        CREATE TABLE IF NOT EXISTS import_statuses (
            import_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_platform TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            total_lectures INTEGER NOT NULL,
            completed_lectures INTEGER NOT NULL,
            failed_lectures INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS import_runs (
            run_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL,
            source_platform TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            total_lectures INTEGER NOT NULL DEFAULT 0,
            completed_lectures INTEGER NOT NULL DEFAULT 0,
            failed_lectures INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_import_runs_course_updated ON import_runs(course_id, updated_at);
        CREATE TABLE IF NOT EXISTS import_events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            event_index INTEGER NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES import_runs(run_id) ON DELETE CASCADE,
            UNIQUE(run_id, event_index)
        );
        CREATE INDEX IF NOT EXISTS idx_import_events_run_index ON import_events(run_id, event_index);
        CREATE TABLE IF NOT EXISTS import_artifacts (
            artifact_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL DEFAULT '',
            artifact_type TEXT NOT NULL,
            artifact_ref TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES import_runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_import_artifacts_course_lecture ON import_artifacts(course_id, lecture_id, artifact_type);
        CREATE TABLE IF NOT EXISTS transcript_segments (
            segment_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_segments_lecture_time ON transcript_segments(course_id, lecture_id, start_seconds);
        CREATE TABLE IF NOT EXISTS knowledge_cards (
            card_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            source_segment_ids_json TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            atom_type TEXT NOT NULL DEFAULT 'concept',
            summary TEXT NOT NULL DEFAULT '',
            review_questions_json TEXT NOT NULL DEFAULT '[]',
            anchor_refs_json TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.75,
            status_lite TEXT NOT NULL DEFAULT 'locked',
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_cards_course_lecture ON knowledge_cards(course_id, lecture_id);
        CREATE TABLE IF NOT EXISTS visual_evidence (
            visual_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            segment_id TEXT NOT NULL DEFAULT '',
            card_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            explanation TEXT NOT NULL,
            image_path TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            provenance TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_visuals_course_lecture ON visual_evidence(course_id, lecture_id);
        CREATE TABLE IF NOT EXISTS notes (
            note_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_notes_course_lecture ON notes(course_id, lecture_id);
        CREATE TABLE IF NOT EXISTS bookmarks (
            bookmark_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_bookmarks_course_type ON bookmarks(course_id, target_type);
        CREATE TABLE IF NOT EXISTS reading_progress (
            course_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            status TEXT NOT NULL,
            last_opened_at TEXT NOT NULL,
            PRIMARY KEY(course_id, lecture_id),
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS chat_threads (
            thread_id TEXT PRIMARY KEY,
            course_id TEXT NOT NULL,
            title TEXT NOT NULL,
            channel TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_chat_threads_course_channel ON chat_threads(course_id, channel, updated_at);
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES chat_threads(thread_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created ON chat_messages(thread_id, created_at);
        CREATE TABLE IF NOT EXISTS chat_events (
            event_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            message_id TEXT,
            event_type TEXT NOT NULL,
            tool_name TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
            FOREIGN KEY(message_id) REFERENCES chat_messages(message_id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chat_events_thread_created ON chat_events(thread_id, created_at);
        CREATE TABLE IF NOT EXISTS web_course_bindings (
            child_course_id TEXT PRIMARY KEY,
            binding_status TEXT NOT NULL,
            mother_course_id TEXT NOT NULL DEFAULT '',
            mother_node_scope TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(child_course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
            CHECK(binding_status IN ('bound', 'unbound', 'blocked')),
            CHECK(binding_status != 'bound' OR mother_course_id != '')
        );
        CREATE INDEX IF NOT EXISTS idx_web_course_bindings_status ON web_course_bindings(binding_status, updated_at);
        """
    )
    _ensure_column(conn, "knowledge_cards", "atom_type", "TEXT NOT NULL DEFAULT 'concept'")
    _ensure_column(conn, "knowledge_cards", "summary", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "knowledge_cards", "review_questions_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "knowledge_cards", "anchor_refs_json", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "knowledge_cards", "confidence", "REAL NOT NULL DEFAULT 0.75")
    _ensure_column(conn, "knowledge_cards", "status_lite", "TEXT NOT NULL DEFAULT 'locked'")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    columns = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if not columns:
        raise ValueError(f"SQLite table not found: {table}")
    return columns


def _dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def _decode_card(row: sqlite3.Row) -> dict[str, Any]:
    payload = _dict(row)
    payload["source_segment_ids"] = json.loads(str(payload.pop("source_segment_ids_json") or "[]"))
    payload["tags"] = json.loads(str(payload.pop("tags_json") or "[]"))
    payload["atom_type"] = str(payload.get("atom_type") or "concept")
    payload["summary"] = str(payload.get("summary") or payload.get("body") or "")
    payload["review_questions"] = json.loads(str(payload.pop("review_questions_json", "[]") or "[]"))
    payload["anchor_refs"] = json.loads(str(payload.pop("anchor_refs_json", "[]") or "[]"))
    payload["confidence"] = float(payload.get("confidence", 0.75) or 0.75)
    payload["status_lite"] = str(payload.get("status_lite") or "locked")
    return payload


def _decode_chat_event(row: sqlite3.Row) -> dict[str, Any]:
    payload = _dict(row)
    payload["message_id"] = str(payload.get("message_id") or "")
    payload["payload"] = json.loads(str(payload.pop("payload_json") or "{}"))
    return payload


def _decode_import_event(row: sqlite3.Row) -> dict[str, Any]:
    payload = _dict(row)
    payload["payload"] = json.loads(str(payload.pop("payload_json") or "{}"))
    return payload


def _decode_import_artifact(row: sqlite3.Row) -> dict[str, Any]:
    payload = _dict(row)
    payload["payload"] = json.loads(str(payload.pop("payload_json") or "{}"))
    return payload


def _skeleton_like(course: dict[str, Any], lectures: list[dict[str, Any]], import_status: dict[str, Any]) -> Any:
    class _Record:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.__dict__.update(payload)

        def to_dict(self) -> dict[str, Any]:
            return dict(self.__dict__)

    class _Skeleton:
        pass

    skeleton = _Skeleton()
    skeleton.course = _Record(course)
    skeleton.lectures = [_Record(lecture) for lecture in lectures]
    skeleton.import_status = _Record(import_status)
    return skeleton
