from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


BILIBILI_BVID_PATTERN = re.compile(r"(BV[0-9A-Za-z]+)")
BILIBILI_VIEW_API_URL = "https://api.bilibili.com/x/web-interface/view"
BILIBILI_PLAYER_V2_API_URL = "https://api.bilibili.com/x/player/v2"
BILIBILI_PLAYER_WBI_V2_API_URL = "https://api.bilibili.com/x/player/wbi/v2"
BILIBILI_AI_SUBTITLE_URL_API = "https://api.bilibili.com/x/player/v2/ai/subtitle/search/stat"
BILIBILI_SUBTITLE_LANGUAGE_PRIORITY = ("ai-zh", "zh-CN", "zh-Hans", "zh", "zh-Hant")

JsonFetcher = Callable[[str, Mapping[str, str], str], Mapping[str, Any]]


@dataclass(frozen=True)
class BilibiliPageMetadata:
    bvid: str
    cid: int
    aid: int | None
    page: int
    video_title: str
    page_title: str


@dataclass(frozen=True)
class BilibiliTimedSubtitle:
    source_url: str
    source_id: str
    video_title: str
    page_title: str
    subtitle_url: str
    timed_lines: list[dict[str, Any]]


def _default_json_fetcher(api_url: str, params: Mapping[str, str], referer: str) -> Mapping[str, Any]:
    encoded_params = urlencode(params)
    request_url = f"{api_url}?{encoded_params}" if encoded_params else api_url
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Referer": referer or "https://www.bilibili.com/",
    }
    cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    request = Request(
        request_url,
        headers=headers,
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - public Bilibili API boundary.
        return json.loads(response.read().decode("utf-8"))


def extract_bilibili_bvid_and_page(source_url: str) -> tuple[str, int]:
    cleaned_url = str(source_url or "").strip()
    match = BILIBILI_BVID_PATTERN.search(cleaned_url)
    if match is None:
        raise ValueError(f"Could not extract Bilibili BV id from URL: {source_url}")
    raw_page = parse_qs(urlparse(cleaned_url).query).get("p", ["1"])[0].strip() or "1"
    try:
        page = int(raw_page)
    except ValueError as exc:
        raise ValueError(f"Invalid Bilibili page number: {raw_page}") from exc
    if page <= 0:
        raise ValueError(f"Bilibili page number must be positive: {page}")
    return match.group(1), page


def resolve_bilibili_page_metadata(
    source_url: str,
    *,
    fetch_json: JsonFetcher | None = None,
) -> BilibiliPageMetadata:
    bvid, page = extract_bilibili_bvid_and_page(source_url)
    json_fetcher = fetch_json or _default_json_fetcher
    payload = json_fetcher(BILIBILI_VIEW_API_URL, {"bvid": bvid}, source_url)
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili view API returned code {payload.get('code')}: {payload}")
    data = payload.get("data") or {}
    if not isinstance(data, Mapping):
        raise RuntimeError("Bilibili view API response is missing data object")
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []
    matched_page = next(
        (
            candidate
            for candidate in pages
            if isinstance(candidate, Mapping) and int(candidate.get("page", 0) or 0) == page
        ),
        None,
    )
    if matched_page is None:
        raise RuntimeError(f"Bilibili page p={page} was not found in view metadata")
    cid = matched_page.get("cid")
    if not cid:
        raise RuntimeError(f"Bilibili page p={page} did not expose a cid")
    aid = data.get("aid")
    return BilibiliPageMetadata(
        bvid=bvid,
        cid=int(cid),
        aid=int(aid) if aid not in (None, "") else None,
        page=page,
        video_title=str(data.get("title", "") or "").strip(),
        page_title=str(matched_page.get("part", "") or "").strip(),
    )


def _select_subtitle(subtitles: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not subtitles:
        raise RuntimeError("Bilibili page did not expose subtitle metadata")
    for language in BILIBILI_SUBTITLE_LANGUAGE_PRIORITY:
        for item in subtitles:
            if str(item.get("lan", "") or "").strip() == language:
                return item
    for item in subtitles:
        if str(item.get("subtitle_url", "") or "").strip():
            return item
    return subtitles[0]


def _normalize_subtitle_url(raw_url: str) -> str:
    cleaned = str(raw_url or "").strip()
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    if cleaned.startswith("/"):
        return f"https://www.bilibili.com{cleaned}"
    return cleaned


def _fetch_subtitle_entries(
    metadata: BilibiliPageMetadata,
    *,
    referer: str,
    fetch_json: JsonFetcher,
) -> list[Mapping[str, Any]]:
    payloads: list[Mapping[str, Any]] = []
    if metadata.aid is not None:
        payloads.append(
            fetch_json(
                BILIBILI_PLAYER_WBI_V2_API_URL,
                {"aid": str(metadata.aid), "cid": str(metadata.cid)},
                referer,
            )
        )
    payloads.append(fetch_json(BILIBILI_PLAYER_V2_API_URL, {"cid": str(metadata.cid), "bvid": metadata.bvid}, referer))
    first_error = ""
    for payload in payloads:
        if payload.get("code") != 0:
            first_error = first_error or f"{payload.get('code')}: {payload}"
            continue
        data = payload.get("data") or {}
        subtitle_payload = data.get("subtitle") if isinstance(data, Mapping) else {}
        subtitles = subtitle_payload.get("subtitles") if isinstance(subtitle_payload, Mapping) else []
        if isinstance(subtitles, list) and subtitles:
            return [item for item in subtitles if isinstance(item, Mapping)]
    raise RuntimeError(first_error or "Bilibili page did not expose subtitle metadata")


def _resolve_ai_subtitle_url(
    metadata: BilibiliPageMetadata,
    *,
    referer: str,
    fetch_json: JsonFetcher,
) -> str:
    if metadata.aid is None:
        return ""
    payload = fetch_json(
        BILIBILI_AI_SUBTITLE_URL_API,
        {"aid": str(metadata.aid), "cid": str(metadata.cid)},
        referer,
    )
    if payload.get("code") != 0:
        return ""
    data = payload.get("data") or {}
    if not isinstance(data, Mapping):
        return ""
    return _normalize_subtitle_url(str(data.get("subtitle_url", "") or ""))


def _normalize_timed_lines(raw_lines: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[float, str]] = set()
    for raw_line in raw_lines:
        text = str(raw_line.get("text", "") or "").strip()
        if not text:
            continue
        try:
            start_seconds = float(raw_line.get("start_seconds", 0.0) or 0.0)
            end_seconds = float(raw_line.get("end_seconds", start_seconds) or start_seconds)
        except (TypeError, ValueError):
            continue
        if end_seconds < start_seconds:
            end_seconds = start_seconds
        key = (round(start_seconds, 3), text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "start_seconds": round(start_seconds, 3),
                "end_seconds": round(end_seconds, 3),
                "text": text,
            }
        )
    normalized.sort(key=lambda item: (float(item["start_seconds"]), str(item["text"])))
    return normalized


def _normalize_subtitle_body(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    body = payload.get("body") if isinstance(payload, Mapping) else []
    if not isinstance(body, list):
        raise RuntimeError("Bilibili subtitle payload is missing body list")
    timed_lines = _normalize_timed_lines(
        [
            {
                "start_seconds": item.get("from", 0.0),
                "end_seconds": item.get("to", item.get("from", 0.0)),
                "text": str(item.get("content", "") or "").strip(),
            }
            for item in body
            if isinstance(item, Mapping)
        ]
    )
    if not timed_lines:
        raise RuntimeError("Bilibili subtitle payload body is empty")
    return timed_lines


def fetch_bilibili_timed_subtitles(
    source_url: str,
    *,
    fetch_json: JsonFetcher | None = None,
) -> BilibiliTimedSubtitle:
    json_fetcher = fetch_json or _default_json_fetcher
    metadata = resolve_bilibili_page_metadata(source_url, fetch_json=json_fetcher)
    subtitles = _fetch_subtitle_entries(metadata, referer=source_url, fetch_json=json_fetcher)
    selected = _select_subtitle(subtitles)
    subtitle_url = _normalize_subtitle_url(str(selected.get("subtitle_url", "") or ""))
    if not subtitle_url and str(selected.get("lan", "") or "").startswith("ai-"):
        subtitle_url = _resolve_ai_subtitle_url(metadata, referer=source_url, fetch_json=json_fetcher)
    if not subtitle_url:
        raise RuntimeError("Bilibili subtitle entry did not expose a usable subtitle_url")
    subtitle_payload = json_fetcher(subtitle_url, {}, source_url)
    return BilibiliTimedSubtitle(
        source_url=str(source_url or "").strip(),
        source_id=metadata.bvid,
        video_title=metadata.video_title or metadata.bvid,
        page_title=metadata.page_title or f"P{metadata.page:03d}",
        subtitle_url=subtitle_url,
        timed_lines=_normalize_subtitle_body(subtitle_payload),
    )
