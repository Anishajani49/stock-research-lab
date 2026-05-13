"""YouTube transcript adapter."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.storage import cache

log = logging.getLogger(__name__)

try:
    from youtube_transcript_api import (
        NoTranscriptFound,
        TranscriptsDisabled,
        YouTubeTranscriptApi,
    )
    _YT_AVAILABLE = True
except Exception:
    _YT_AVAILABLE = False


_VIDEO_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    m = _VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)
    # If the url *is* just an ID
    s = url.strip()
    if len(s) == 11 and re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    return None


def fetch_transcript(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False, "error": None, "url": url,
        "video_id": None, "text": "", "language": "",
    }
    if not _YT_AVAILABLE:
        result["error"] = "youtube-transcript-api not installed"
        return result

    vid = extract_video_id(url)
    if not vid:
        result["error"] = "Could not parse YouTube video ID"
        return result
    result["video_id"] = vid

    cached = cache.get("youtube", vid, ttl_seconds=60 * 60 * 24)
    if cached is not None:
        return cached

    try:
        chunks = YouTubeTranscriptApi.get_transcript(vid, languages=["en", "en-US", "en-GB"])
        text = " ".join(c.get("text", "").strip() for c in chunks if c.get("text"))
        result.update({"ok": True, "text": text[:15000], "language": "en"})
    except (TranscriptsDisabled, NoTranscriptFound):
        result["error"] = "Transcript unavailable for this video"
    except Exception as e:
        log.warning("yt transcript failed: %s", e)
        result["error"] = f"transcript error: {e!s}"

    cache.set("youtube", vid, result)
    return result


def fetch_many(urls: list[str]) -> list[dict[str, Any]]:
    return [fetch_transcript(u) for u in urls]
