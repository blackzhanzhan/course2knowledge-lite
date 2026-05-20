from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


BILIBILI_COLLECTION_API_URL = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"
BILIBILI_VIEW_API_URL = "https://api.bilibili.com/x/web-interface/view"
BILIBILI_COLLECTION_WEB_LOCATION = "333.1387"
BILIBILI_VIDEO_URL_TEMPLATE = "https://www.bilibili.com/video/{bvid}"
BILIBILI_VIDEO_PAGE_URL_TEMPLATE = "https://www.bilibili.com/video/{bvid}?p={page}"
BILIBILI_BVID_PATTERN = re.compile(r"(BV[0-9A-Za-z]+)")
LISTS_COLLECTION_PATTERN = re.compile(r"^/(?P<mid>\d+)/lists/(?P<season_id>\d+)$")
CHANNEL_COLLECTION_PATTERN = re.compile(r"^/(?P<mid>\d+)/channel/collectiondetail$")

JsonFetcher = Callable[[str, Mapping[str, str], str], Mapping[str, Any]]


@dataclass(frozen=True)
class BilibiliCollectionUrl:
    source_url: str
    mid: str
    season_id: str


@dataclass(frozen=True)
class BilibiliVideoRef:
    sequence: int
    bvid: str
    title: str
    source_url: str


@dataclass(frozen=True)
class BilibiliCollection:
    source_url: str
    title: str
    videos: list[BilibiliVideoRef]


def is_bilibili_collection_url(source_url: str) -> bool:
    parsed = urlparse(str(source_url or "").strip())
    if parsed.netloc.lower() != "space.bilibili.com":
        return False
    path = parsed.path.rstrip("/")
    if LISTS_COLLECTION_PATTERN.match(path):
        return True
    if CHANNEL_COLLECTION_PATTERN.match(path):
        return bool(parse_qs(parsed.query).get("sid", [""])[0].strip())
    return False


def is_bilibili_video_url(source_url: str) -> bool:
    parsed = urlparse(str(source_url or "").strip())
    if parsed.netloc.lower() not in {"www.bilibili.com", "bilibili.com", "m.bilibili.com"}:
        return False
    return BILIBILI_BVID_PATTERN.search(parsed.path) is not None


def parse_bilibili_collection_url(source_url: str) -> BilibiliCollectionUrl:
    cleaned_url = str(source_url or "").strip()
    parsed = urlparse(cleaned_url)
    if parsed.netloc.lower() != "space.bilibili.com":
        raise ValueError(f"Not a Bilibili collection URL: {source_url}")
    path = parsed.path.rstrip("/")
    lists_match = LISTS_COLLECTION_PATTERN.match(path)
    if lists_match is not None:
        return BilibiliCollectionUrl(
            source_url=cleaned_url,
            mid=lists_match.group("mid"),
            season_id=lists_match.group("season_id"),
        )
    channel_match = CHANNEL_COLLECTION_PATTERN.match(path)
    if channel_match is not None:
        season_id = parse_qs(parsed.query).get("sid", [""])[0].strip()
        if season_id:
            return BilibiliCollectionUrl(
                source_url=cleaned_url,
                mid=channel_match.group("mid"),
                season_id=season_id,
            )
    raise ValueError(f"Unsupported Bilibili collection URL: {source_url}")


def extract_bilibili_bvid(source_url: str) -> str:
    cleaned_url = str(source_url or "").strip()
    match = BILIBILI_BVID_PATTERN.search(cleaned_url)
    if match is None:
        raise ValueError(f"Could not extract Bilibili BV id from URL: {source_url}")
    return match.group(1)


def _default_json_fetcher(api_url: str, params: Mapping[str, str], referer: str) -> Mapping[str, Any]:
    request_url = f"{api_url}?{urlencode(params)}"
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
    with urlopen(request, timeout=30) as response:  # noqa: S310 - user-provided Bilibili URL boundary.
        return json.loads(response.read().decode("utf-8"))


def _normalize_video_ref(sequence: int, item: Mapping[str, Any]) -> BilibiliVideoRef | None:
    bvid = str(item.get("bvid", "") or "").strip()
    if not bvid:
        return None
    title = str(item.get("title", "") or item.get("part", "") or bvid).strip()
    return BilibiliVideoRef(
        sequence=sequence,
        bvid=bvid,
        title=title,
        source_url=BILIBILI_VIDEO_URL_TEMPLATE.format(bvid=bvid),
    )


def _collection_title(data: Mapping[str, Any], season_id: str) -> str:
    meta = data.get("meta") if isinstance(data.get("meta"), Mapping) else {}
    return str(
        meta.get("name")
        or meta.get("title")
        or data.get("name")
        or data.get("title")
        or f"bilibili-collection-{season_id}"
    ).strip()


def _video_page_title(video_title: str, page: Mapping[str, Any]) -> str:
    part = str(page.get("part", "") or "").strip()
    if part:
        return part
    page_no = int(page.get("page", 0) or 0)
    return f"{video_title} P{page_no:03d}" if page_no > 0 else video_title


def _normalize_page_ref(sequence: int, *, bvid: str, video_title: str, page: Mapping[str, Any]) -> BilibiliVideoRef | None:
    try:
        page_no = int(page.get("page", 0) or 0)
    except (TypeError, ValueError):
        page_no = 0
    if page_no <= 0:
        return None
    return BilibiliVideoRef(
        sequence=sequence,
        bvid=bvid,
        title=_video_page_title(video_title, page),
        source_url=BILIBILI_VIDEO_PAGE_URL_TEMPLATE.format(bvid=bvid, page=page_no),
    )


def _iter_ugc_season_pages(data: Mapping[str, Any]) -> list[BilibiliVideoRef]:
    season = data.get("ugc_season") if isinstance(data.get("ugc_season"), Mapping) else {}
    sections = season.get("sections") if isinstance(season.get("sections"), list) else []
    videos: list[BilibiliVideoRef] = []
    seen_urls: set[str] = set()
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        episodes = section.get("episodes") if isinstance(section.get("episodes"), list) else []
        for episode in episodes:
            if not isinstance(episode, Mapping):
                continue
            bvid = str(episode.get("bvid", "") or "").strip()
            if not bvid:
                continue
            arc = episode.get("arc") if isinstance(episode.get("arc"), Mapping) else {}
            episode_title = str(episode.get("title") or arc.get("title") or bvid).strip()
            pages = episode.get("pages") if isinstance(episode.get("pages"), list) else []
            if not pages:
                page = episode.get("page") if isinstance(episode.get("page"), Mapping) else {}
                pages = [page] if page else []
            if not pages:
                pages = [{"page": 1, "part": episode_title}]
            for page in pages:
                if not isinstance(page, Mapping):
                    continue
                page_for_title = dict(page)
                part = str(page_for_title.get("part", "") or "").strip()
                if part and part != episode_title:
                    page_for_title["part"] = f"{episode_title} / {part}"
                elif not part:
                    page_for_title["part"] = episode_title
                candidate = _normalize_page_ref(
                    len(videos) + 1,
                    bvid=bvid,
                    video_title=episode_title,
                    page=page_for_title,
                )
                if candidate is None or candidate.source_url in seen_urls:
                    continue
                seen_urls.add(candidate.source_url)
                videos.append(candidate)
    return videos


def expand_bilibili_collection_url(
    source_url: str,
    *,
    page_size: int = 30,
    fetch_json: JsonFetcher | None = None,
) -> BilibiliCollection:
    parsed_url = parse_bilibili_collection_url(source_url)
    json_fetcher = fetch_json or _default_json_fetcher
    current_page = 1
    title = ""
    expected_total = 0
    videos: list[BilibiliVideoRef] = []
    seen_bvids: set[str] = set()

    while True:
        payload = json_fetcher(
            BILIBILI_COLLECTION_API_URL,
            {
                "mid": parsed_url.mid,
                "season_id": parsed_url.season_id,
                "sort_reverse": "false",
                "page_num": str(current_page),
                "page_size": str(page_size),
                "web_location": BILIBILI_COLLECTION_WEB_LOCATION,
            },
            parsed_url.source_url,
        )
        if payload.get("code") != 0:
            raise RuntimeError(f"Bilibili collection API returned code {payload.get('code')}: {payload}")
        data = payload.get("data") or {}
        if not isinstance(data, Mapping):
            raise RuntimeError("Bilibili collection API response is missing data object")
        if not title:
            title = _collection_title(data, parsed_url.season_id)
        archives = data.get("archives") if isinstance(data.get("archives"), list) else []
        for item in archives:
            if not isinstance(item, Mapping):
                continue
            candidate = _normalize_video_ref(len(videos) + 1, item)
            if candidate is None or candidate.bvid in seen_bvids:
                continue
            seen_bvids.add(candidate.bvid)
            videos.append(candidate)
        page = data.get("page") if isinstance(data.get("page"), Mapping) else {}
        expected_total = int(page.get("total", 0) or expected_total or 0)
        if not archives:
            break
        if expected_total and len(videos) >= expected_total:
            break
        if not expected_total and len(archives) < page_size:
            break
        current_page += 1

    if not videos:
        raise RuntimeError(f"Bilibili collection {parsed_url.season_id} did not expose any videos")
    return BilibiliCollection(source_url=parsed_url.source_url, title=title, videos=videos)


def expand_bilibili_video_url(
    source_url: str,
    *,
    fetch_json: JsonFetcher | None = None,
) -> BilibiliCollection:
    cleaned_url = str(source_url or "").strip()
    bvid = extract_bilibili_bvid(cleaned_url)
    json_fetcher = fetch_json or _default_json_fetcher
    payload = json_fetcher(BILIBILI_VIEW_API_URL, {"bvid": bvid}, cleaned_url)
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili view API returned code {payload.get('code')}: {payload}")
    data = payload.get("data") or {}
    if not isinstance(data, Mapping):
        raise RuntimeError("Bilibili view API response is missing data object")
    title = str(data.get("title", "") or bvid).strip()
    pages = data.get("pages") if isinstance(data.get("pages"), list) else []

    videos: list[BilibiliVideoRef] = []
    if len(pages) > 1:
        for page in pages:
            if not isinstance(page, Mapping):
                continue
            candidate = _normalize_page_ref(len(videos) + 1, bvid=bvid, video_title=title, page=page)
            if candidate is not None:
                videos.append(candidate)
    else:
        videos = _iter_ugc_season_pages(data)
        if not videos:
            for page in pages or [{"page": 1, "part": title}]:
                if not isinstance(page, Mapping):
                    continue
                candidate = _normalize_page_ref(len(videos) + 1, bvid=bvid, video_title=title, page=page)
                if candidate is not None:
                    videos.append(candidate)
        else:
            season = data.get("ugc_season") if isinstance(data.get("ugc_season"), Mapping) else {}
            title = str(season.get("title") or title).strip()

    if not videos:
        raise RuntimeError(f"Bilibili video {bvid} did not expose any pages or series episodes")
    return BilibiliCollection(source_url=cleaned_url, title=title, videos=videos)


def expand_bilibili_source_url(
    source_url: str,
    *,
    fetch_json: JsonFetcher | None = None,
) -> BilibiliCollection:
    if is_bilibili_collection_url(source_url):
        return expand_bilibili_collection_url(source_url, fetch_json=fetch_json)
    if is_bilibili_video_url(source_url):
        return expand_bilibili_video_url(source_url, fetch_json=fetch_json)
    raise ValueError(f"Unsupported Bilibili source URL: {source_url}")
