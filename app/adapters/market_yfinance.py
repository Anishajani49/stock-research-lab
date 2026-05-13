"""Market data adapter using yfinance — NSE/BSE aware."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.config import settings
from app.storage import cache

log = logging.getLogger(__name__)

try:
    import yfinance as yf  # noqa: F401

    _YF_AVAILABLE = True
except Exception:
    _YF_AVAILABLE = False


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if pd.isna(f):
            return None
        return f
    except Exception:
        return None


def normalize_indian_ticker(ticker: str, exchange: str = "auto") -> list[str]:
    """Return a list of candidate yfinance tickers to try, in order.

    Rules:
    - If ticker already ends with '.NS' or '.BO', use as-is.
    - If exchange='NSE' → try 'TICKER.NS'.
    - If exchange='BSE' → try 'TICKER.BO'.
    - If exchange='auto' → try '.NS' first, fall back to '.BO'.
    """
    t = ticker.strip().upper()
    if t.endswith(".NS") or t.endswith(".BO"):
        return [t]

    ex = (exchange or "auto").upper()
    if ex == "NSE":
        return [f"{t}.NS"]
    if ex == "BSE":
        return [f"{t}.BO"]
    # auto
    return [f"{t}.NS", f"{t}.BO"]


def _fetch_one(candidate: str, timeframe: str) -> dict[str, Any] | None:
    """Try one candidate ticker. Return a result dict or None if empty/invalid."""
    import yfinance as yf

    tk = yf.Ticker(candidate)
    hist = tk.history(period=timeframe, auto_adjust=False)
    if hist is None or hist.empty:
        return None

    hist = hist.reset_index()
    if "Date" in hist.columns:
        hist["Date"] = hist["Date"].astype(str)
    elif "Datetime" in hist.columns:
        hist["Date"] = hist["Datetime"].astype(str)

    ohlcv_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in hist.columns]
    ohlcv = hist[ohlcv_cols].to_dict(orient="records")

    meta: dict[str, Any] = {}
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    exch_suffix = candidate.rsplit(".", 1)[-1] if "." in candidate else ""
    detected_exchange = "NSE" if exch_suffix == "NS" else "BSE" if exch_suffix == "BO" else info.get("exchange") or ""

    meta["long_name"] = info.get("longName") or info.get("shortName") or candidate
    meta["sector"] = info.get("sector")
    meta["industry"] = info.get("industry")
    meta["market_cap"] = _safe_float(info.get("marketCap"))
    meta["pe"] = _safe_float(info.get("trailingPE"))
    meta["currency"] = info.get("currency") or settings.DEFAULT_CURRENCY
    meta["exchange"] = detected_exchange
    meta["yf_symbol"] = candidate

    close = hist["Close"].astype(float)
    last = float(close.iloc[-1])
    first = float(close.iloc[0])
    high = float(close.max())
    low = float(close.min())
    pct = ((last - first) / first * 100.0) if first else 0.0
    summary = {
        "last_close": last,
        "period_return_pct": round(pct, 2),
        "period_high": high,
        "period_low": low,
        "n_bars": int(len(hist)),
        "start_date": str(hist["Date"].iloc[0]) if "Date" in hist.columns else None,
        "end_date": str(hist["Date"].iloc[-1]) if "Date" in hist.columns else None,
    }

    return {
        "ok": True, "error": None,
        "ticker": candidate,
        "ohlcv": ohlcv,
        "meta": meta,
        "summary": summary,
    }


def fetch_market(ticker: str, timeframe: str = "6mo", exchange: str = "auto") -> dict[str, Any]:
    """Fetch OHLCV + company metadata for an Indian ticker.

    Tries NSE (.NS) first, then BSE (.BO) when exchange='auto'.
    """
    result: dict[str, Any] = {
        "ok": False, "error": None,
        "ticker": ticker, "timeframe": timeframe,
        "ohlcv": [], "meta": {}, "summary": {},
    }

    if not _YF_AVAILABLE:
        result["error"] = "yfinance not installed"
        return result

    cache_key = f"{ticker}_{exchange}_{timeframe}"
    cached = cache.get("market", cache_key, ttl_seconds=60 * 30)
    if cached is not None:
        return cached

    candidates = normalize_indian_ticker(ticker, exchange)
    last_error = f"No price data for ticker '{ticker}'"

    for cand in candidates:
        try:
            out = _fetch_one(cand, timeframe)
            if out is not None:
                out["timeframe"] = timeframe
                cache.set("market", cache_key, out)
                return out
            last_error = f"No data on {cand}"
        except Exception as e:
            log.warning("yfinance fetch failed for %s: %s", cand, e)
            last_error = f"yfinance error on {cand}: {e!s}"

    result["error"] = last_error
    return result
