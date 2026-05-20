from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import format_timestamp_anchor, parse_srt_blocks_from_text


def _line_to_timed_line(line: dict[str, Any]) -> dict[str, Any]:
    start_ms = int(line.get("start_ms", 0) or 0)
    end_ms = int(line.get("end_ms", start_ms) or start_ms)
    return {
        "line_id": int(line.get("line_id", 0) or 0),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "start_seconds": round(start_ms / 1000.0, 3),
        "end_seconds": round(end_ms / 1000.0, 3),
        "text": str(line.get("text", "")).strip(),
    }


def load_timed_lines_from_srt(srt_path: Path) -> list[dict[str, Any]]:
    return [
        _line_to_timed_line(line)
        for line in parse_srt_blocks_from_text(srt_path.read_text(encoding="utf-8-sig"))
    ]


def build_subtitle_chunk_manifest_from_srt(
    *,
    srt_path: Path,
    lecture_id: str,
    max_lines_per_chunk: int = 120,
    overlap_lines: int = 6,
    max_chars_per_chunk: int = 1800,
) -> dict[str, Any]:
    timed_lines = load_timed_lines_from_srt(srt_path)
    step = max(1, max_lines_per_chunk - overlap_lines)
    chunks: list[dict[str, Any]] = []
    start_index = 0
    while start_index < len(timed_lines):
        chunk_lines = timed_lines[start_index : start_index + max_lines_per_chunk]
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
        if source_line_ids[-1] >= len(timed_lines):
            break
        start_index += step
    return {
        "lecture_id": lecture_id,
        "srt_path": str(srt_path),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
