from __future__ import annotations

from typing import Any, Iterable, Mapping

from .models import LectureRecord, TranscriptSegmentRecord


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
