from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


class ValidationError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...] | str):
        if isinstance(errors, str):
            normalized = [errors]
        else:
            normalized = [str(item) for item in errors]
        super().__init__("; ".join(normalized))
        self.errors = normalized


def format_timestamp_anchor(seconds: float | int | str) -> str:
    try:
        value = max(float(seconds), 0.0)
    except (TypeError, ValueError):
        value = 0.0
    total_seconds = int(value)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


_SRT_BLOCK_RE = re.compile(
    r"(?P<index>\d+)\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{1,3})\s*\n"
    r"(?P<text>.*?)(?=\n\s*\n|\Z)",
    flags=re.DOTALL,
)


def _srt_timestamp_to_ms(raw_value: str) -> int:
    cleaned = str(raw_value or "").strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) != 3:
        return 0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return 0
    return int(round(((hours * 3600) + (minutes * 60) + seconds) * 1000))


def parse_srt_blocks_from_text(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    for fallback_index, match in enumerate(_SRT_BLOCK_RE.finditer(normalized), start=1):
        line_text = " ".join(
            line.strip()
            for line in match.group("text").splitlines()
            if line.strip()
        )
        if not line_text:
            continue
        try:
            line_id = int(match.group("index"))
        except ValueError:
            line_id = fallback_index
        blocks.append(
            {
                "line_id": line_id,
                "start_ms": _srt_timestamp_to_ms(match.group("start")),
                "end_ms": _srt_timestamp_to_ms(match.group("end")),
                "text": line_text,
            }
        )
    return blocks


@dataclass
class RequestRetryTelemetryRecorder:
    records: list[dict[str, Any]] = field(default_factory=list)

    def record_attempt(self, **payload: Any) -> None:
        self.records.append({"event": "attempt", **dict(payload)})

    def record_success(self, **payload: Any) -> None:
        self.records.append({"event": "success", **dict(payload)})

    def record_failure(self, **payload: Any) -> None:
        self.records.append({"event": "failure", **dict(payload)})

