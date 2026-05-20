from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READING_PROGRESS_STATUSES = {"not_started", "reading", "read"}
CHAT_MESSAGE_ROLES = {"user", "assistant", "system", "tool"}
CHAT_EVENT_TYPES = {"message_delta", "tool_start", "tool_result", "media", "done", "error", "teaching_control"}
WEB_COURSE_BINDING_STATUSES = {"bound", "unbound", "blocked"}
IMPORT_RUN_STATUSES = {"queued", "running", "completed", "partial", "failed", "cancelled"}


@dataclass(frozen=True)
class CourseRecord:
    course_id: str
    title: str
    source_url: str
    source_platform: str
    import_status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "import_status": self.import_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class LectureRecord:
    lecture_id: str
    course_id: str
    title: str
    source_url: str
    sequence: int
    source_id: str
    duration_seconds: int | None
    read_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "lecture_id": self.lecture_id,
            "course_id": self.course_id,
            "title": self.title,
            "source_url": self.source_url,
            "sequence": self.sequence,
            "source_id": self.source_id,
            "duration_seconds": self.duration_seconds,
            "read_status": self.read_status,
        }


@dataclass(frozen=True)
class ImportStatusRecord:
    import_id: str
    course_id: str
    source_url: str
    source_platform: str
    status: str
    stage: str
    total_lectures: int
    completed_lectures: int
    failed_lectures: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "import_id": self.import_id,
            "course_id": self.course_id,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "status": self.status,
            "stage": self.stage,
            "total_lectures": self.total_lectures,
            "completed_lectures": self.completed_lectures,
            "failed_lectures": self.failed_lectures,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ImportRunRecord:
    run_id: str
    course_id: str
    source_url: str
    source_platform: str
    status: str
    stage: str
    total_lectures: int
    completed_lectures: int
    failed_lectures: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "course_id": self.course_id,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "status": self.status,
            "stage": self.stage,
            "total_lectures": self.total_lectures,
            "completed_lectures": self.completed_lectures,
            "failed_lectures": self.failed_lectures,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ImportEventRecord:
    event_id: str
    run_id: str
    event_index: int
    stage: str
    status: str
    event_type: str
    message: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_index": self.event_index,
            "stage": self.stage,
            "status": self.status,
            "event_type": self.event_type,
            "message": self.message,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ImportArtifactRecord:
    artifact_id: str
    run_id: str
    course_id: str
    lecture_id: str
    artifact_type: str
    artifact_ref: str
    status: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "artifact_type": self.artifact_type,
            "artifact_ref": self.artifact_ref,
            "status": self.status,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class TranscriptSegmentRecord:
    segment_id: str
    lecture_id: str
    start_seconds: float
    end_seconds: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "lecture_id": self.lecture_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }


@dataclass(frozen=True)
class KnowledgeCardRecord:
    card_id: str
    course_id: str
    lecture_id: str
    title: str
    body: str
    source_segment_ids: list[str]
    tags: list[str]
    atom_type: str = "concept"
    summary: str = ""
    review_questions: list[str] | None = None
    anchor_refs: list[str] | None = None
    confidence: float = 0.75
    status_lite: str = "locked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "title": self.title,
            "body": self.body,
            "source_segment_ids": list(self.source_segment_ids),
            "tags": list(self.tags),
            "atom_type": self.atom_type,
            "summary": self.summary or self.body,
            "review_questions": list(self.review_questions or []),
            "anchor_refs": list(self.anchor_refs or []),
            "confidence": float(self.confidence),
            "status_lite": self.status_lite,
        }


@dataclass(frozen=True)
class VisualEvidenceRecord:
    visual_id: str
    course_id: str
    lecture_id: str
    segment_id: str
    card_id: str
    title: str
    explanation: str
    image_path: str
    source_url: str
    provenance: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_id": self.visual_id,
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "segment_id": self.segment_id,
            "card_id": self.card_id,
            "title": self.title,
            "explanation": self.explanation,
            "image_path": self.image_path,
            "source_url": self.source_url,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class NoteRecord:
    note_id: str
    course_id: str
    lecture_id: str
    body: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "body": self.body,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class BookmarkRecord:
    bookmark_id: str
    target_type: str
    target_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bookmark_id": self.bookmark_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ReadingProgressRecord:
    course_id: str
    lecture_id: str
    status: str
    last_opened_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "status": self.status,
            "last_opened_at": self.last_opened_at,
        }


@dataclass(frozen=True)
class ChatThreadRecord:
    thread_id: str
    course_id: str
    title: str
    channel: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "course_id": self.course_id,
            "title": self.title,
            "channel": self.channel,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ChatMessageRecord:
    message_id: str
    thread_id: str
    role: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ChatEventRecord:
    event_id: str
    thread_id: str
    message_id: str
    event_type: str
    tool_name: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "thread_id": self.thread_id,
            "message_id": self.message_id,
            "event_type": self.event_type,
            "tool_name": self.tool_name,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class WebCourseBindingRecord:
    child_course_id: str
    binding_status: str
    mother_course_id: str
    mother_node_scope: str
    note: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "child_course_id": self.child_course_id,
            "binding_status": self.binding_status,
            "mother_course_id": self.mother_course_id,
            "mother_node_scope": self.mother_node_scope,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class CourseSkeleton:
    course: CourseRecord
    lectures: list[LectureRecord]
    import_status: ImportStatusRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "course": self.course.to_dict(),
            "lectures": [lecture.to_dict() for lecture in self.lectures],
            "import_status": self.import_status.to_dict(),
        }
