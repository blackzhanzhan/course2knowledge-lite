from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .models import LectureRecord, TranscriptSegmentRecord

_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？.!?])\s+")


def build_transcript_segments(
    *,
    lecture: LectureRecord | Mapping[str, Any],
    timed_lines: Iterable[Mapping[str, Any]],
) -> list[TranscriptSegmentRecord]:
    lecture_id = lecture.lecture_id if isinstance(lecture, LectureRecord) else str(lecture.get("lecture_id", ""))
    if not lecture_id:
        raise ValueError("lecture_id is required to build transcript segments")
    segments: list[TranscriptSegmentRecord] = []
    for index, line in enumerate(timed_lines, start=1):
        text = str(line.get("text", "") or "").strip()
        if not text:
            continue
        start_seconds = round(float(line.get("start_seconds", 0.0) or 0.0), 3)
        end_seconds = round(float(line.get("end_seconds", start_seconds) or start_seconds), 3)
        if end_seconds < start_seconds:
            end_seconds = start_seconds
        segments.append(
            TranscriptSegmentRecord(
                segment_id=f"{lecture_id}::seg::{index:05d}",
                lecture_id=lecture_id,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                text=text,
            )
        )
    if not segments:
        raise ValueError(f"No transcript segments were built for lecture {lecture_id}")
    return segments


def build_manual_transcript_segments(
    *,
    lecture: LectureRecord | Mapping[str, Any],
    transcript_text: str,
    segment_seconds: float = 6.0,
) -> list[TranscriptSegmentRecord]:
    lecture_id = lecture.lecture_id if isinstance(lecture, LectureRecord) else str(lecture.get("lecture_id", ""))
    if not lecture_id:
        raise ValueError("lecture_id is required to build manual transcript segments")
    chunks = _split_manual_transcript_text(transcript_text)
    if not chunks:
        raise ValueError("transcript_text did not contain any usable text")
    duration = max(float(segment_seconds or 0.0), 1.0)
    return [
        TranscriptSegmentRecord(
            segment_id=f"{lecture_id}::manual::{index:05d}",
            lecture_id=lecture_id,
            start_seconds=round((index - 1) * duration, 3),
            end_seconds=round(index * duration, 3),
            text=text,
        )
        for index, text in enumerate(chunks, start=1)
    ]


def _split_manual_transcript_text(transcript_text: str) -> list[str]:
    paragraphs = [line.strip() for line in str(transcript_text or "").splitlines() if line.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        candidates = [part.strip() for part in _SENTENCE_BOUNDARY.split(paragraph) if part.strip()]
        if len(candidates) <= 1:
            chunks.append(paragraph)
        else:
            chunks.extend(candidates)
    return chunks
