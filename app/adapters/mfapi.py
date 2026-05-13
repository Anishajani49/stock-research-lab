"""Indian Mutual Fund adapter using mfapi.in (wraps AMFI NAV data)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.storage import cache

log = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8))
def _http_get_json(url: str) -> Any:
    with httpx.Client(
        timeout=settings.HTTP_TIMEOUT,
        headers={"User-Agent": "stock-research-assistant/India"},
        follow_redirects=True,
    ) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def search_scheme(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search for a mutual fund scheme by name. Returns list of {schemeCode, schemeName}."""
    q = query.strip()
    if not q:
        return []
    cached = cache.get("mf_search", q.lower(), ttl_seconds=60 * 60 * 24)
    if cached is not None:
        return cached[:limit]
    url = f"{settings.MFAPI_BASE_URL}/mf/search?q={q}"
    try:
        data = _http_get_json(url)
        if not isinstance(data, list):
            return []
        cache.set("mf_search", q.lower(), data)
        return data[:limit]
    except Exception as e:
        log.warning("MF search failed: %s", e)
        return []


def _timeframe_to_days(timeframe: str) -> int | None:
    """Map our timeframe strings to day counts. None = all."""
    tf = timeframe.strip().lower()
    mapping = {
        "1d": 2, "5d": 7, "1mo": 35, "3mo": 100, "6mo": 200,
        "1y": 380, "2y": 760, "5y": 1900, "10y": 3800, "ytd": 400,
    }
    if tf == "max":
        return None
    return mapping.get(tf)


def fetch_nav_history(scheme_code: str, timeframe: str = "6mo") -> dict[str, Any]:
    """Fetch NAV history for an Indian MF and shape it like the equity adapter output.

    Returns a dict with keys: ok, error, ticker, ohlcv, meta, summary.
    'ohlcv' will only contain Date + Close (NAV); no volume/high/low.
    """
    result: dict[str, Any] = {
        "ok": False, "error": None,
        "ticker": scheme_code, "timeframe": timeframe,
        "ohlcv": [], "meta": {}, "summary": {},
    }
    if not scheme_code or not str(scheme_code).strip().isdigit():
        result["error"] = f"Invalid scheme code '{scheme_code}' (must be numeric)"
        return result

    cache_key = f"{scheme_code}_{timeframe}"
    cached = cache.get("mf_history", cache_key, ttl_seconds=60 * 60 * 6)
    if cached is not None:
        return cached

    url = f"{settings.MFAPI_BASE_URL}/mf/{scheme_code}"
    try:
        payload = _http_get_json(url)
    except Exception as e:
        result["error"] = f"mfapi error: {e!s}"
        return result

    meta_in = payload.get("meta") or {}
    data = payload.get("data") or []
    if not data:
        result["error"] = "No NAV data returned"
        return result

    # mfapi returns newest-first with date 'dd-mm-yyyy' and nav as string.
    # Convert to oldest-first and filter by timeframe.
    import datetime as _dt

    records = []
    for row in data:
        try:
            d = _dt.datetime.strptime(row["date"], "%d-%m-%Y").date()
            nav = float(row["nav"])
            records.append({"Date": d.isoformat(), "Close": nav})
        except Exception:
            continue

    if not records:
        result["error"] = "Could not parse any NAV rows"
        return result

    records.sort(key=lambda r: r["Date"])  # oldest first

    days = _timeframe_to_days(timeframe)
    if days:
        cutoff = records[-1]["Date"]
        cutoff_dt = _dt.date.fromisoformat(cutoff) - _dt.timedelta(days=days)
        records = [r for r in records if _dt.date.fromisoformat(r["Date"]) >= cutoff_dt]

    if not records:
        result["error"] = "No NAV data in requested timeframe"
        return result

    last = records[-1]["Close"]
    first = records[0]["Close"]
    high = max(r["Close"] for r in records)
    low = min(r["Close"] for r in records)
    pct = ((last - first) / first * 100.0) if first else 0.0

    meta = {
        "long_name": meta_in.get("scheme_name") or f"Scheme {scheme_code}",
        "fund_house": meta_in.get("fund_house"),
        "scheme_type": meta_in.get("scheme_type"),
        "scheme_category": meta_in.get("scheme_category"),
        "scheme_code": meta_in.get("scheme_code") or scheme_code,
        "isin_growth": meta_in.get("isin_growth"),
        "isin_div": meta_in.get("isin_div_reinvestment"),
        "sector": meta_in.get("scheme_category") or "Mutual Fund",
        "industry": "Mutual Fund",
        "exchange": "AMFI",
        "currency": "INR",
        "yf_symbol": None,
    }

    summary = {
        "last_close": float(last),
        "period_return_pct": round(pct, 2),
        "period_high": float(high),
        "period_low": float(low),
        "n_bars": int(len(records)),
        "start_date": records[0]["Date"],
        "end_date": records[-1]["Date"],
    }

    out = {
        "ok": True, "error": None,
        "ticker": str(scheme_code),
        "timeframe": timeframe,
        "ohlcv": records,
        "meta": meta,
        "summary": summary,
    }
    cache.set("mf_history", cache_key, out)
    return out


def resolve_scheme(query: str) -> tuple[str | None, str | None]:
    """Best-effort: if `query` is numeric, use as-is. Otherwise search and pick top match.

    Returns (scheme_code, scheme_name) or (None, None).
    """
    q = query.strip()
    if q.isdigit():
        return q, None
    hits = search_scheme(q, limit=1)
    if hits:
        return str(hits[0].get("schemeCode")), hits[0].get("schemeName")
    return None, None
