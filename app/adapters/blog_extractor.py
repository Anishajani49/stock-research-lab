"""Blog/article readable body extractor using trafilatura.

Resolves redirects (notably Google News wrapper URLs) before extracting,
so the actual publisher article body is captured.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.storage import cache

log = logging.getLogger(__name__)

try:
    import trafilatura  # noqa: F401
    _TRAF_AVAILABLE = True
except Exception:
    _TRAF_AVAILABLE = False


_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15"
)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=8))
def _fetch(url: str) -> tuple[str, str]:
    """Return (final_url, html_body). Follows all redirects."""
    with httpx.Client(
        timeout=settings.HTTP_TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    ) as c:
        r = c.get(url)
        r.raise_for_status()
        return str(r.url), r.text


def _is_google_news(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host.endswith("news.google.com")


def _resolve_final_url(url: str) -> str:
    """For Google News URLs, follow redirects to the real publisher URL."""
    if not _is_google_news(url):
        return url
    try:
        with httpx.Client(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _UA, "Accept-Language": "en-IN,en;q=0.9"},
        ) as c:
            r = c.get(url)
            final = str(r.url)
            if not _is_google_news(final):
                return final
    except Exception as e:
        log.debug("Google News redirect resolve failed: %s", e)
    return url


def extract_article(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False, "error": None,
        "url": url, "final_url": url,
        "title": "", "text": "", "author": "", "date": "", "source_domain": "",
    }
    if not _TRAF_AVAILABLE:
        result["error"] = "trafilatura not installed"
        return result

    cached = cache.get("articles", url, ttl_seconds=60 * 60 * 6)
    if cached is not None:
        return cached

    # Resolve Google News wrapper → real publisher URL
    real_url = _resolve_final_url(url)
    result["final_url"] = real_url

    try:
        final_url, html = _fetch(real_url)
        result["final_url"] = final_url
    except Exception as e:
        result["error"] = f"fetch failed: {e!s}"
        cache.set("articles", url, result)
        return result

    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=False,  # favour recall — news articles are often short
            deduplicate=True,
        ) or ""
        meta = trafilatura.extract_metadata(html)

        source_domain = ""
        try:
            source_domain = (urlparse(result["final_url"]).hostname or "").lower().lstrip("www.")
        except Exception:
            pass

        result.update({
            "ok": bool(extracted and len(extracted) > 200),
            "title": (meta.title if meta else "") or "",
            "author": (meta.author if meta else "") or "",
            "date": (meta.date if meta else "") or "",
            "text": extracted[:12000],
            "source_domain": source_domain,
        })
        if not result["ok"]:
            result["error"] = f"content too short ({len(extracted)} chars)"
    except Exception as e:
        log.warning("trafilatura failed: %s", e)
        result["error"] = f"extract error: {e!s}"

    cache.set("articles", url, result)
    return result


def extract_many(urls: list[str], limit: int | None = None) -> list[dict[str, Any]]:
    limit = limit or settings.ARTICLE_MAX_ITEMS
    out: list[dict[str, Any]] = []
    for url in urls[:limit]:
        out.append(extract_article(url))
    return out
