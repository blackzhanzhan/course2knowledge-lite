from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from .content import build_lecture_reader_payload, search_transcript_segments
from .models import (
    READING_PROGRESS_STATUSES,
    BookmarkRecord,
    CourseSkeleton,
    KnowledgeCardRecord,
    NoteRecord,
    ReadingProgressRecord,
    TranscriptSegmentRecord,
    VisualEvidenceRecord,
)

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
        missing_count = max(lecture_count - covered_count, 0)
        return {
            "course": dict(course),
            "course_id": course_id,
            "lecture_count": lecture_count,
            "covered_lecture_count": covered_count,
            "missing_lecture_count": missing_count,
            "total_segment_count": total_segments,
            "coverage_ratio": round(covered_count / lecture_count, 4) if lecture_count else 0.0,
            "lectures": lecture_summaries,
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
    ) -> dict[str, Any]:
        self.read_course(course_id)
        selected_lecture_id = str(lecture_id or "").strip()
        lectures = self.read_lectures(course_id)
        if selected_lecture_id:
            lectures = [lecture for lecture in lectures if str(lecture.get("lecture_id") or "") == selected_lecture_id]
            if not lectures:
                raise ValueError(f"lecture not found: {selected_lecture_id}")
        generated_cards: list[dict[str, Any]] = []
        for lecture in lectures:
            current_lecture_id = str(lecture.get("lecture_id") or "")
            for segment in self.read_transcript_segments_if_exists(course_id, current_lecture_id):
                generated_cards.append(
                    self._build_knowledge_card(course_id=course_id, lecture=lecture, segment=segment).to_dict()
                )
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
        self._write_json(self._knowledge_cards_path(course_id), cards)
        return {
            "course_id": course_id,
            "card_count": len(cards),
            "generated_card_count": len(generated_cards),
            "cards": cards,
            "path": str(self._knowledge_cards_path(course_id)),
        }

    def list_knowledge_cards(self, *, course_id: str, lecture_id: str = "") -> list[dict[str, Any]]:
        cards = self._read_json_list_if_exists(self._knowledge_cards_path(course_id))
        if lecture_id:
            return [card for card in cards if str(card.get("lecture_id") or "") == lecture_id]
        return cards

    def read_knowledge_card(self, course_id: str, card_id: str) -> dict[str, Any]:
        cleaned_card_id = str(card_id or "").strip()
        if not cleaned_card_id:
            raise ValueError("card_id is required")
        for card in self.list_knowledge_cards(course_id=course_id):
            if str(card.get("card_id") or "") == cleaned_card_id:
                return dict(card)
        raise ValueError(f"card not found: {cleaned_card_id}")

    def write_visual_evidence_records(
        self,
        course_id: str,
        records: list[VisualEvidenceRecord | dict[str, Any]],
    ) -> str:
        self.read_course(course_id)
        normalized = [self._normalize_visual_evidence(course_id, record) for record in records]
        normalized.sort(key=lambda item: (str(item.get("lecture_id") or ""), str(item.get("visual_id") or "")))
        self._write_json(self._visual_evidence_path(course_id), normalized)
        return str(self._visual_evidence_path(course_id))

    def list_visual_evidence(
        self,
        *,
        course_id: str,
        lecture_id: str = "",
        query: str = "",
    ) -> list[dict[str, Any]]:
        items = self._read_json_list_if_exists(self._visual_evidence_path(course_id))
        if lecture_id:
            items = [item for item in items if str(item.get("lecture_id") or "") == lecture_id]
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
        for item in self.list_visual_evidence(course_id=course_id):
            if str(item.get("visual_id") or "") == cleaned_visual_id:
                return dict(item)
        raise ValueError(f"visual evidence not found: {cleaned_visual_id}")

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
        )
        notes = self.list_notes(course_id=course_id)
        if any(str(item.get("note_id") or "") == note.note_id for item in notes):
            raise ValueError(f"note_id already exists: {note.note_id}")
        notes.append(note.to_dict())
        self._write_json(self._notes_path(course_id), notes)
        return note.to_dict()

    def list_notes(self, *, course_id: str, lecture_id: str = "") -> list[dict[str, Any]]:
        notes = self._read_json_list_if_exists(self._notes_path(course_id))
        if lecture_id:
            return [note for note in notes if str(note.get("lecture_id") or "") == lecture_id]
        return notes

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
        notes = self.list_notes(course_id=course_id)
        updated: dict[str, Any] | None = None
        for note in notes:
            if str(note.get("note_id") or "") != cleaned_note_id:
                continue
            note["body"] = cleaned_body
            note["updated_at"] = now or self._utc_now()
            updated = dict(note)
            break
        if updated is None:
            raise ValueError(f"note not found: {cleaned_note_id}")
        self._write_json(self._notes_path(course_id), notes)
        return updated

    def delete_note(self, course_id: str, note_id: str) -> dict[str, Any]:
        cleaned_note_id = str(note_id or "").strip()
        if not cleaned_note_id:
            raise ValueError("note_id is required")
        notes = self.list_notes(course_id=course_id)
        kept = [note for note in notes if str(note.get("note_id") or "") != cleaned_note_id]
        deleted = len(kept) != len(notes)
        self._write_json(self._notes_path(course_id), kept)
        return {"deleted": deleted, "note_id": cleaned_note_id}

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
        created_at = now or self._utc_now()
        bookmark = BookmarkRecord(
            bookmark_id=bookmark_id or f"bookmark_{uuid4().hex[:12]}",
            target_type=cleaned_type,
            target_id=cleaned_target,
            created_at=created_at,
        )
        bookmarks = self.list_bookmarks(course_id=course_id)
        if any(str(item.get("bookmark_id") or "") == bookmark.bookmark_id for item in bookmarks):
            raise ValueError(f"bookmark_id already exists: {bookmark.bookmark_id}")
        bookmarks.append(bookmark.to_dict())
        self._write_json(self._bookmarks_path(course_id), bookmarks)
        return bookmark.to_dict()

    def list_bookmarks(self, *, course_id: str, target_type: str = "") -> list[dict[str, Any]]:
        bookmarks = self._read_json_list_if_exists(self._bookmarks_path(course_id))
        if target_type:
            return [item for item in bookmarks if str(item.get("target_type") or "") == target_type]
        return bookmarks

    def delete_bookmark(self, course_id: str, bookmark_id: str) -> dict[str, Any]:
        cleaned_bookmark_id = str(bookmark_id or "").strip()
        if not cleaned_bookmark_id:
            raise ValueError("bookmark_id is required")
        bookmarks = self.list_bookmarks(course_id=course_id)
        kept = [item for item in bookmarks if str(item.get("bookmark_id") or "") != cleaned_bookmark_id]
        deleted = len(kept) != len(bookmarks)
        self._write_json(self._bookmarks_path(course_id), kept)
        return {"deleted": deleted, "bookmark_id": cleaned_bookmark_id}

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
        progress = self.list_reading_progress(course_id=course_id)
        record = ReadingProgressRecord(
            course_id=course_id,
            lecture_id=lecture_id,
            status=cleaned_status,
            last_opened_at=now or self._utc_now(),
        ).to_dict()
        replaced = False
        for index, item in enumerate(progress):
            if str(item.get("lecture_id") or "") == lecture_id:
                progress[index] = record
                replaced = True
                break
        if not replaced:
            progress.append(record)
        self._write_json(self._reading_progress_path(course_id), progress)
        self._update_lecture_read_status(course_id, lecture_id, cleaned_status)
        return record

    def get_reading_progress(self, course_id: str, lecture_id: str) -> dict[str, Any]:
        self._ensure_lecture_exists(course_id, lecture_id)
        for item in self.list_reading_progress(course_id=course_id):
            if str(item.get("lecture_id") or "") == lecture_id:
                return dict(item)
        return ReadingProgressRecord(
            course_id=course_id,
            lecture_id=lecture_id,
            status="not_started",
            last_opened_at="",
        ).to_dict()

    def list_reading_progress(self, *, course_id: str) -> list[dict[str, Any]]:
        return self._read_json_list_if_exists(self._reading_progress_path(course_id))

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

    def _update_lecture_read_status(self, course_id: str, lecture_id: str, status: str) -> None:
        lectures = self.read_lectures(course_id)
        changed = False
        for lecture in lectures:
            if str(lecture.get("lecture_id") or "") == lecture_id:
                lecture["read_status"] = status
                changed = True
                break
        if changed:
            self._write_json(self.root / "courses" / course_id / "lectures.json", lectures)

    def _notes_path(self, course_id: str) -> Path:
        return self.root / "courses" / course_id / "notes.json"

    def _bookmarks_path(self, course_id: str) -> Path:
        return self.root / "courses" / course_id / "bookmarks.json"

    def _reading_progress_path(self, course_id: str) -> Path:
        return self.root / "courses" / course_id / "reading_progress.json"

    def _knowledge_cards_path(self, course_id: str) -> Path:
        return self.root / "courses" / course_id / "knowledge_cards.json"

    def _visual_evidence_path(self, course_id: str) -> Path:
        return self.root / "courses" / course_id / "visual_evidence.json"

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

    def _build_knowledge_card(
        self,
        *,
        course_id: str,
        lecture: dict[str, Any],
        segment: dict[str, Any],
    ) -> KnowledgeCardRecord:
        segment_id = str(segment.get("segment_id") or "").strip()
        if not segment_id:
            raise ValueError("segment_id is required to build a knowledge card")
        text = str(segment.get("text") or "").strip()
        card_id = f"card_{hashlib.sha1(segment_id.encode('utf-8')).hexdigest()[:12]}"
        lecture_title = str(lecture.get("title") or "").strip()
        title = _card_title(text, fallback=lecture_title or card_id)
        return KnowledgeCardRecord(
            card_id=card_id,
            course_id=course_id,
            lecture_id=str(lecture.get("lecture_id") or segment.get("lecture_id") or ""),
            title=title,
            body=text,
            source_segment_ids=[segment_id],
            tags=_card_tags(text),
        )

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def _read_json_list_if_exists(cls, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        payload = cls._read_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"JSON payload is not a list: {path}")
        return [dict(item) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _safe_filename(raw_name: str) -> str:
        cleaned = _UNSAFE_FILENAME_CHARS.sub("_", str(raw_name or "").strip()).strip(" ._")
        return cleaned or "untitled"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_generated_card(card: dict[str, Any]) -> bool:
    return str(card.get("card_id") or "").startswith("card_") and bool(card.get("source_segment_ids"))


def _card_title(text: str, *, fallback: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return fallback
    first_sentence = re.split(r"(?<=[.!?])\s+|\n+", cleaned, maxsplit=1)[0].strip()
    title = first_sentence or cleaned or fallback
    if len(title) > 72:
        title = f"{title[:69].rstrip()}..."
    return title


def _card_tags(text: str) -> list[str]:
    tags: list[str] = []
    for term in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", str(text or "")):
        normalized = term.strip()
        if normalized and normalized.lower() not in {item.lower() for item in tags}:
            tags.append(normalized)
        if len(tags) >= 8:
            break
    return tags


def _visual_search_matches(item: dict[str, Any], *, cleaned_query: str, query_terms: list[str]) -> bool:
    searchable = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("explanation") or ""),
            str(item.get("provenance") or ""),
        ]
    ).lower()
    if cleaned_query in searchable:
        return True
    return any(term in searchable for term in query_terms)


def _query_terms(query: str) -> list[str]:
    return [term for term in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", query.lower()) if len(term) >= 2]
