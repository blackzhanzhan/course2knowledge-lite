from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READING_PROGRESS_STATUSES = {"not_started", "reading", "read"}


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "course_id": self.course_id,
            "lecture_id": self.lecture_id,
            "title": self.title,
            "body": self.body,
            "source_segment_ids": list(self.source_segment_ids),
            "tags": list(self.tags),
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
