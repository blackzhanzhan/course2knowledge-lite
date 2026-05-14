from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .content import build_lecture_reader_payload, search_transcript_segments
from .models import CourseSkeleton, TranscriptSegmentRecord

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


class JsonCourseStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write_skeleton(self, skeleton: CourseSkeleton) -> dict[str, str]:
        course_id = skeleton.course.course_id
        course_root = self.root / "courses" / course_id
        imports_root = self.root / "imports"
        course_root.mkdir(parents=True, exist_ok=True)
        imports_root.mkdir(parents=True, exist_ok=True)

        course_path = course_root / "course.json"
        lectures_path = course_root / "lectures.json"
        import_status_path = imports_root / f"{skeleton.import_status.import_id}.json"

        self._write_json(course_path, skeleton.course.to_dict())
        self._write_json(lectures_path, [lecture.to_dict() for lecture in skeleton.lectures])
        self._write_json(import_status_path, skeleton.import_status.to_dict())
        return {
            "course": str(course_path),
            "lectures": str(lectures_path),
            "import_status": str(import_status_path),
        }

    def read_course(self, course_id: str) -> dict[str, Any]:
        return self._read_json(self.root / "courses" / course_id / "course.json")

    def read_lectures(self, course_id: str) -> list[dict[str, Any]]:
        payload = self._read_json(self.root / "courses" / course_id / "lectures.json")
        if not isinstance(payload, list):
            raise ValueError(f"Lectures payload is not a list for course {course_id}")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def read_import_status(self, import_id: str) -> dict[str, Any]:
        return self._read_json(self.root / "imports" / f"{import_id}.json")

    def write_transcript_segments(
        self,
        course_id: str,
        lecture_id: str,
        segments: list[TranscriptSegmentRecord],
    ) -> str:
        course_root = self.root / "courses" / course_id
        course_root.mkdir(parents=True, exist_ok=True)
        path = course_root / f"{self._safe_filename(lecture_id)}.segments.json"
        self._write_json(path, [segment.to_dict() for segment in segments])
        return str(path)

    def read_transcript_segments(self, course_id: str, lecture_id: str) -> list[dict[str, Any]]:
        payload = self._read_json(self.root / "courses" / course_id / f"{self._safe_filename(lecture_id)}.segments.json")
        if not isinstance(payload, list):
            raise ValueError(f"Transcript segment payload is not a list for lecture {lecture_id}")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def read_transcript_segments_if_exists(self, course_id: str, lecture_id: str) -> list[dict[str, Any]]:
        path = self.root / "courses" / course_id / f"{self._safe_filename(lecture_id)}.segments.json"
        if not path.exists():
            return []
        payload = self._read_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"Transcript segment payload is not a list for lecture {lecture_id}")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def read_all_transcript_segments(self, course_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            str(lecture.get("lecture_id", "") or ""): self.read_transcript_segments_if_exists(
                course_id,
                str(lecture.get("lecture_id", "") or ""),
            )
            for lecture in self.read_lectures(course_id)
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

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _safe_filename(raw_name: str) -> str:
        cleaned = _UNSAFE_FILENAME_CHARS.sub("_", str(raw_name or "").strip()).strip(" ._")
        return cleaned or "untitled"
