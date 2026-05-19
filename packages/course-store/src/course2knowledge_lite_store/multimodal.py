from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MultimodalConfigError(ValueError):
    """Raised when a Lite multimodal anchor cannot be interpreted."""


@dataclass(frozen=True)
class LiteAnchorFrameWindow:
    anchor_id: str
    center_seconds: float
    start_seconds: float
    end_seconds: float
    suggested_timestamp: str
    source_segment_ids: tuple[str, ...]
    source_line_ids: tuple[int, ...]
    evidence_quote: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "center_seconds": self.center_seconds,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "suggested_timestamp": self.suggested_timestamp,
            "source_segment_ids": list(self.source_segment_ids),
            "source_line_ids": list(self.source_line_ids),
            "evidence_quote": self.evidence_quote,
        }


def parse_anchor_timestamp(raw_value: str) -> float:
    cleaned = str(raw_value or "").strip()
    if not cleaned:
        raise MultimodalConfigError("multimodal anchor timestamp must be non-empty")
    normalized = cleaned.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = "0", parts[0], parts[1]
    else:
        raise MultimodalConfigError(f"multimodal anchor timestamp is invalid: {cleaned}")
    try:
        total = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise MultimodalConfigError(f"multimodal anchor timestamp is invalid: {cleaned}") from exc
    return max(0.0, round(total, 3))


def format_anchor_timestamp(seconds: float) -> str:
    total = max(0.0, float(seconds or 0.0))
    whole = int(total)
    millis = int(round((total - whole) * 1000))
    if millis >= 1000:
        whole += 1
        millis -= 1000
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if millis:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def build_lite_anchor_frame_windows(
    *,
    anchors: list[dict[str, Any]],
    lead_seconds: float = 2.0,
    lag_seconds: float = 8.0,
) -> list[LiteAnchorFrameWindow]:
    windows: list[LiteAnchorFrameWindow] = []
    for index, anchor in enumerate(anchors or [], start=1):
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchor_id") or f"anchor_{index:03d}").strip()
        suggested_timestamp = str(anchor.get("suggested_screenshot_timestamp") or "").strip()
        if not suggested_timestamp:
            continue
        center_seconds = parse_anchor_timestamp(suggested_timestamp)
        start_seconds = max(0.0, round(center_seconds - max(float(lead_seconds), 0.0), 3))
        end_seconds = max(start_seconds, round(center_seconds + max(float(lag_seconds), 0.0), 3))
        windows.append(
            LiteAnchorFrameWindow(
                anchor_id=anchor_id,
                center_seconds=center_seconds,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                suggested_timestamp=suggested_timestamp,
                source_segment_ids=tuple(
                    str(item).strip()
                    for item in (anchor.get("source_segment_ids") or [])
                    if str(item).strip()
                ),
                source_line_ids=tuple(
                    int(item)
                    for item in (anchor.get("source_line_ids") or [])
                    if str(item).strip()
                ),
                evidence_quote=str(anchor.get("evidence_quote") or "").strip(),
            )
        )
    return windows


__all__ = [
    "LiteAnchorFrameWindow",
    "MultimodalConfigError",
    "build_lite_anchor_frame_windows",
    "format_anchor_timestamp",
    "parse_anchor_timestamp",
]
