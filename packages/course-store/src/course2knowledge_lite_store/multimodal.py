from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any


class MultimodalConfigError(ValueError):
    """Raised when a Lite multimodal anchor cannot be interpreted."""


class MultimodalDependencyError(RuntimeError):
    """Raised when a required local multimodal dependency is unavailable."""


class MultimodalExtractionError(RuntimeError):
    """Raised when ffmpeg cannot extract frames from a real media file."""


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


def require_ffmpeg() -> str:
    resolved = shutil.which("ffmpeg")
    if resolved:
        return resolved
    raise MultimodalDependencyError("ffmpeg is required for Lite multimodal keyframe extraction")


def resolve_lite_source_media(*, media_path: str = "") -> str:
    cleaned = str(media_path or "").strip()
    if not cleaned:
        raise MultimodalConfigError("Lite multimodal extraction requires a local media_path")
    resolved = Path(cleaned).expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise MultimodalConfigError(f"Lite multimodal source media is missing: {resolved}")
    return str(resolved)


def extract_lite_candidate_frames_for_windows(
    *,
    media_path: str,
    windows: list[LiteAnchorFrameWindow],
    output_root: str,
    sample_every_seconds: float = 1.0,
) -> dict[str, list[str]]:
    source_media = resolve_lite_source_media(media_path=media_path)
    ffmpeg = require_ffmpeg()
    output_dir = Path(str(output_root or "").strip()).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    fps_value = 1.0 / max(float(sample_every_seconds), 0.1)
    results: dict[str, list[str]] = {}
    for window in windows:
        anchor_dir = output_dir / _safe_anchor_dir(window.anchor_id)
        anchor_dir.mkdir(parents=True, exist_ok=True)
        output_pattern = anchor_dir / "frame_%03d.jpg"
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{window.start_seconds:.3f}",
                "-to",
                f"{window.end_seconds:.3f}",
                "-i",
                source_media,
                "-vf",
                f"fps={fps_value:.4f}",
                "-q:v",
                "2",
                str(output_pattern),
            ],
            text=True,
            capture_output=True,
            timeout=1800,
            check=False,
        )
        if completed.returncode != 0:
            detail = str(completed.stderr or completed.stdout or "").strip()
            raise MultimodalExtractionError(
                f"ffmpeg could not extract Lite frames for {window.anchor_id}: {detail[:300]}"
            )
        results[window.anchor_id] = sorted(str(path.resolve()) for path in anchor_dir.glob("frame_*.jpg"))
    return results


def _safe_anchor_dir(raw_value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(raw_value or "").strip())
    return cleaned.strip("._") or "anchor"


__all__ = [
    "LiteAnchorFrameWindow",
    "MultimodalConfigError",
    "MultimodalDependencyError",
    "MultimodalExtractionError",
    "build_lite_anchor_frame_windows",
    "extract_lite_candidate_frames_for_windows",
    "format_anchor_timestamp",
    "parse_anchor_timestamp",
    "require_ffmpeg",
    "resolve_lite_source_media",
]
