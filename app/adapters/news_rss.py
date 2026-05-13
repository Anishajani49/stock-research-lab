"""Indian financial news adapter — per-source coverage.

Strategy:
  For each ticker, run a Google News (India locale) RSS search filtered by
  `site:<domain>` for every configured Indian news outlet. This gives us
  ticker-specific articles from each source (not just whatever Google decides
  to surface).

Sources (configurable via INDIA_NEWS_SOURCES env var):
  - Economic Times
  - Business Today
  - MoneyControl
  - LiveMint
  - Business Standard
  - Hindu BusinessLine
  - Financial Express
  - CNBC TV18
  - NDTV Profit
  - Zee Business

Fallback:
  - Plain Google News India search (no site filter)
  - Broad market feeds (MoneyControl, ET, Mint, Business Standard RSS)
    — filtered to ticker/company-name mentions
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.config import settings
from app.storage import cache

log = logging.getLogger(__name__)

try:
    import feedparser  # noqa: F401
    _FP_AVAILABLE = True
except Exception:
    _FP_AVAILABLE = False


# --- Default Indian finance outlets ------------------------------------------
# (display_name, domain)
_DEFAULT_SOURCES: list[tuple[str, str]] = [
    ("Economic Times",      "economictimes.indiatimes.com"),
    ("Business Today",      "businesstoday.in"),
    ("MoneyControl",        "moneycontrol.com"),
    ("LiveMint",            "livemint.com"),
    ("Business Standard",   "business-standard.com"),
    ("Hindu BusinessLine",  "thehindubusinessline.com"),
    ("Financial Express",   "financialexpress.com"),
    ("CNBC TV18",           "cnbctv18.com"),
    ("NDTV Profit",         "ndtvprofit.com"),
    ("Zee Business",        "zeebiz.com"),
]


def _configured_sources() -> list[tuple[str, str]]:
    """Allow override via env: INDIA_NEWS_SOURCES='ET|economictimes.indiatimes.com,BT|businesstoday.in'."""
    raw = os.getenv("INDIA_NEWS_SOURCES", "").strip()
    if not raw:
        return _DEFAULT_SOURCES
    out: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if "|" in chunk:
            name, domain = chunk.split("|", 1)
            out.append((name.strip(), domain.strip()))
    return out or _DEFAULT_SOURCES


# --- Broad market-wide feeds (used only as fallback context) ------------------
INDIA_BROAD_FEEDS: list[tuple[str, str]] = [
    ("MoneyControl — Top News",
     "https://www.moneycontrol.com/rss/MCtopnews.xml"),
    ("MoneyControl — Business",
     "https://www.moneycontrol.com/rss/business.xml"),
    ("Economic Times — Markets",
     "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Economic Times — Stocks",
     "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("LiveMint — Markets",
     "https://www.livemint.com/rss/markets"),
    ("Business Standard — Markets",
     "https://www.business-standard.com/rss/markets-106.rss"),
    ("Business Today — Markets",
     "https://www.businesstoday.in/rss/markets"),
    ("Hindu BusinessLine — Markets",
     "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
    ("Financial Express — Market",
     "https://www.financialexpress.com/market/feed/"),
]


# --- Helpers -----------------------------------------------------------------

def _strip_suffix(ticker: str) -> str:
    t = ticker.strip().upper()
    for s in (".NS", ".BO"):
        if t.endswith(s):
            return t[: -len(s)]
    return t


def _google_news_india(query: str) -> str:
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def _parse_time(entry: Any) -> str:
    for key in ("published", "updated"):
        val = entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if val:
            return str(val)
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: str) -> str:
    """Canonicalize a URL for deduplication (strip UTM/query, normalize host)."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().lstrip("www.")
        path = p.path.rstrip("/")
        return f"{host}{path}"
    except Exception:
        return url.lower()


def _infer_source_from_url(url: str, fallback: str = "") -> str:
    try:
        host = (urlparse(url).hostname or "").lower().lstrip("www.")
        for name, domain in _configured_sources():
            if host.endswith(domain):
                return name
    except Exception:
        pass
    return fallback or "Unknown"


def _collect_from_feed(
    url: str,
    max_items: int,
    seen_keys: set[str],
    source_fallback: str = "",
) -> list[dict[str, Any]]:
    import feedparser
    items: list[dict[str, Any]] = []
    try:
        d = feedparser.parse(url)
    except Exception as e:
        log.warning("RSS parse failed for %s: %s", url, e)
        return items

    feed_title = getattr(d.feed, "title", "") if hasattr(d, "feed") else ""

    for e in d.entries[: max_items * 3]:
        link = getattr(e, "link", "") or ""
        if not link:
            continue
        key = _normalize_url(link)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Prefer outlet inferred from the article URL (works for Google News feeds,
        # where feed.title is always just "Google News").
        source = _infer_source_from_url(link, fallback=source_fallback or feed_title)

        items.append({
            "title": (getattr(e, "title", "") or "").strip(),
            "url": link,
            "source": source,
            "published": _parse_time(e),
            "snippet": (getattr(e, "summary", "") or "")[:500],
        })
        if len(items) >= max_items:
            break
    return items


def _looks_relevant(item: dict[str, Any], ticker_bare: str, long_name: str | None) -> bool:
    hay = (item.get("title", "") + " " + item.get("snippet", "")).lower()
    if ticker_bare and ticker_bare.lower() in hay:
        return True
    if long_name:
        parts = [p for p in long_name.lower().split() if len(p) > 3]
        for p in parts[:3]:
            if p in hay:
                return True
    return False


def _build_query(ticker_bare: str, long_name: str | None) -> str:
    parts = [ticker_bare]
    if long_name:
        # Drop suffixes that hurt searches ("Limited", "Ltd.", "Corp.")
        ln = long_name
        for suf in (" Limited", " LIMITED", " Ltd.", " LTD.", " Ltd", " LTD",
                    " Corporation", " Corp.", " Inc."):
            if ln.endswith(suf):
                ln = ln[: -len(suf)]
        ln = ln.strip()
        if ln and ln.lower() != ticker_bare.lower():
            parts.append(f'"{ln}"')
    return " OR ".join(parts) if len(parts) > 1 else parts[0]


# --- Public API --------------------------------------------------------------

def fetch_news(
    ticker: str,
    max_items: int | None = None,
    long_name: str | None = None,
) -> dict[str, Any]:
    """Fetch India-focused news for a ticker, aggregating across major outlets.

    Returns {ok, error, items, per_source_counts}.
    """
    max_items = max_items or settings.NEWS_MAX_ITEMS
    per_source_cap = max(2, int(os.getenv("NEWS_PER_SOURCE_MAX", "3")))

    result: dict[str, Any] = {
        "ok": False, "error": None,
        "items": [], "per_source_counts": {},
    }

    if not _FP_AVAILABLE:
        result["error"] = "feedparser not installed"
        return result

    cache_key = f"{ticker}_{long_name or ''}_v2"
    cached = cache.get("news", cache_key, ttl_seconds=60 * 15)
    if cached is not None:
        return cached

    ticker_bare = _strip_suffix(ticker)
    base_query = _build_query(ticker_bare, long_name)
    seen: set[str] = set()
    bucket: list[dict[str, Any]] = []
    per_source_counts: dict[str, int] = {}

    # 1. Per-source ticker search via Google News India with site: filter
    sources = _configured_sources()
    tasks: list[tuple[str, str]] = []
    for name, domain in sources:
        q = f"{base_query} site:{domain}"
        tasks.append((name, _google_news_india(q)))

    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as pool:
        futures = {
            pool.submit(_collect_from_feed, url, per_source_cap, seen, name): name
            for name, url in tasks
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                items = fut.result()
            except Exception as e:
                log.warning("Source %s failed: %s", name, e)
                items = []
            if items:
                for it in items:
                    # Force the display name onto the item so downstream UI
                    # clearly shows the outlet.
                    it["source"] = it.get("source") or name
                bucket.extend(items)
                per_source_counts[name] = len(items)

    # 2. General Google News India search (no site filter) to catch anything missed
    if len(bucket) < max_items:
        extra = _collect_from_feed(
            _google_news_india(base_query + " stock India"),
            max_items - len(bucket),
            seen,
            source_fallback="Google News India",
        )
        bucket.extend(extra)
        if extra:
            per_source_counts.setdefault("Google News India", 0)
            per_source_counts["Google News India"] += len(extra)

    # 3. Fallback: broad Indian market feeds — only relevant items
    if len(bucket) < max_items:
        for label, url in INDIA_BROAD_FEEDS:
            if len(bucket) >= max_items:
                break
            batch = _collect_from_feed(url, max_items, seen, source_fallback=label)
            for item in batch:
                if _looks_relevant(item, ticker_bare, long_name):
                    bucket.append(item)
                    per_source_counts[item.get("source", label)] = \
                        per_source_counts.get(item.get("source", label), 0) + 1
                    if len(bucket) >= max_items:
                        break

    # Sort by published desc (best-effort string sort of parsed dates)
    from email.utils import parsedate_to_datetime

    def _sort_key(item: dict[str, Any]):
        try:
            dt = parsedate_to_datetime(item.get("published") or "")
            return dt.timestamp()
        except Exception:
            return 0.0

    bucket.sort(key=_sort_key, reverse=True)
    bucket = bucket[:max_items]

    result["ok"] = True
    result["items"] = bucket
    result["per_source_counts"] = per_source_counts
    if not bucket:
        result["error"] = "No India-focused headlines found"

    cache.set("news", cache_key, result)
    return result


def fetch_market_wide_news(max_items: int = 10) -> dict[str, Any]:
    """Optional helper: pull India-wide market context (no ticker filter)."""
    if not _FP_AVAILABLE:
        return {"ok": False, "error": "feedparser not installed", "items": []}
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for label, url in INDIA_BROAD_FEEDS:
        batch = _collect_from_feed(url, max_items, seen, source_fallback=label)
        items.extend(batch)
        if len(items) >= max_items:
            break
    return {"ok": True, "error": None, "items": items[:max_items]}
