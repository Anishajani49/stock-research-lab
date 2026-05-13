"""Fundamentals + upcoming-events adapter.

Pulls the same kind of data Zerodha / Groww surface in their stock pages —
all from public, free sources:

  - yfinance `Ticker.info`     → forwardPE, dividend yield, ROE, debt/equity,
                                 book value, payout, beta, 52w high/low, etc.
  - yfinance `Ticker.calendar` → next earnings date + EPS estimates
  - yfinance `Ticker.actions`  → recent / upcoming dividends + splits

We never log into Zerodha or Groww (auth-walled, terms-of-service issues) —
we hit the same upstream sources their public pages are built from.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.storage import cache

log = logging.getLogger(__name__)

try:
    import pandas as pd
    import yfinance as yf  # noqa: F401

    _YF_AVAILABLE = True
except Exception:
    _YF_AVAILABLE = False


# ---------------------------------------------------------------------------
# helpers

def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        # pandas NaN check without importing
        if f != f:  # NaN != NaN
            return None
        return f
    except Exception:
        return None


def _as_iso_date(v: Any) -> str | None:
    """Best-effort ISO-date string. Accepts datetime, pandas Timestamp, int (epoch), str."""
    if v is None:
        return None
    try:
        # pandas Timestamp / datetime
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        # epoch seconds
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(float(v), tz=timezone.utc).strftime("%Y-%m-%d")
        # string — try a few formats
        s = str(v)
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return s[:10]
    except Exception:
        return None


def _days_until(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).days
        return delta
    except Exception:
        return None


# ---------------------------------------------------------------------------
# upcoming events

def _earnings_events_from_calendar(tk) -> list[dict[str, Any]]:
    """Best-effort upcoming earnings extraction from yfinance Ticker.calendar.

    yfinance returns this in different shapes across versions: sometimes a dict,
    sometimes a DataFrame. We handle both defensively.
    """
    out: list[dict[str, Any]] = []
    try:
        cal = tk.calendar
    except Exception as e:
        log.debug("calendar fetch failed: %s", e)
        return out
    if cal is None:
        return out

    # dict shape (newer yfinance)
    if isinstance(cal, dict):
        ed = cal.get("Earnings Date") or cal.get("earningsDate")
        if isinstance(ed, list) and ed:
            ed_iso = _as_iso_date(ed[0])
        else:
            ed_iso = _as_iso_date(ed)
        if ed_iso:
            eps_low = _safe_float(cal.get("Earnings Low") or cal.get("earningsLow"))
            eps_high = _safe_float(cal.get("Earnings High") or cal.get("earningsHigh"))
            eps_avg = _safe_float(cal.get("Earnings Average") or cal.get("earningsAverage"))
            rev_avg = _safe_float(cal.get("Revenue Average") or cal.get("revenueAverage"))
            note_bits = []
            if eps_avg is not None:
                note_bits.append(f"EPS estimate ~{eps_avg:.2f}")
            if eps_low is not None and eps_high is not None:
                note_bits.append(f"range {eps_low:.2f}–{eps_high:.2f}")
            if rev_avg is not None and rev_avg > 0:
                note_bits.append(f"revenue est ~{rev_avg/1e7:,.0f} Cr")
            out.append({
                "kind": "earnings",
                "date": ed_iso,
                "days_until": _days_until(ed_iso),
                "title": "Quarterly earnings",
                "note": "; ".join(note_bits) if note_bits else "",
            })
        return out

    # DataFrame shape (older yfinance)
    try:
        if hasattr(cal, "T") and not cal.empty:
            df = cal.T if cal.shape[0] < cal.shape[1] else cal
            for _, row in df.iterrows():
                ed = row.get("Earnings Date")
                ed_iso = _as_iso_date(ed)
                if not ed_iso:
                    continue
                out.append({
                    "kind": "earnings",
                    "date": ed_iso,
                    "days_until": _days_until(ed_iso),
                    "title": "Quarterly earnings",
                    "note": "",
                })
    except Exception as e:
        log.debug("calendar dataframe parse failed: %s", e)
    return out


def _dividend_events_from_info(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull next ex-div / dividend date + last dividend amount from Ticker.info."""
    out: list[dict[str, Any]] = []
    if not info:
        return out
    ex_iso = _as_iso_date(info.get("exDividendDate"))
    pay_iso = _as_iso_date(info.get("dividendDate"))
    last_amt = _safe_float(info.get("lastDividendValue"))
    last_date = _as_iso_date(info.get("lastDividendDate"))

    # Forward-looking: ex-div in the future
    if ex_iso:
        days = _days_until(ex_iso)
        if days is not None and days >= -2:
            out.append({
                "kind": "ex_dividend",
                "date": ex_iso,
                "days_until": days,
                "title": "Ex-dividend date",
                "note": (
                    f"Buy by the day before to qualify for the next dividend. "
                    f"Last paid: ₹{last_amt:.2f}/share" + (f" on {last_date}" if last_date else "")
                    if last_amt else
                    "Buy by the day before to qualify for the next dividend."
                ),
            })

    if pay_iso:
        days = _days_until(pay_iso)
        if days is not None and days >= -2:
            out.append({
                "kind": "dividend_payment",
                "date": pay_iso,
                "days_until": days,
                "title": "Dividend payment",
                "note": (
                    f"Approx ₹{last_amt:.2f}/share if the next payout matches the last one."
                    if last_amt else "Dividend payout date."
                ),
            })
    return out


def _split_events_from_info(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Last split — informational, mostly historical context."""
    out: list[dict[str, Any]] = []
    if not info:
        return out
    iso = _as_iso_date(info.get("lastSplitDate"))
    factor = info.get("lastSplitFactor")
    if iso and factor:
        out.append({
            "kind": "last_split",
            "date": iso,
            "days_until": _days_until(iso),
            "title": f"Last stock split ({factor})",
            "note": "Historical reference — affects how older chart prices compare to today's.",
        })
    return out


# ---------------------------------------------------------------------------
# fundamentals snapshot

def _fundamentals_from_info(info: dict[str, Any]) -> dict[str, Any]:
    """Beginner-relevant ratios + price stats — same fields Zerodha/Groww show."""
    if not info:
        return {}
    fund = {
        # valuation
        "trailing_pe":   _safe_float(info.get("trailingPE")),
        "forward_pe":    _safe_float(info.get("forwardPE")),
        "peg_ratio":     _safe_float(info.get("pegRatio")),
        "price_to_book": _safe_float(info.get("priceToBook")),
        "book_value":    _safe_float(info.get("bookValue")),
        "market_cap":    _safe_float(info.get("marketCap")),
        # income / profitability
        "dividend_yield":   _safe_float(info.get("dividendYield")),
        "payout_ratio":     _safe_float(info.get("payoutRatio")),
        "return_on_equity": _safe_float(info.get("returnOnEquity")),
        "return_on_assets": _safe_float(info.get("returnOnAssets")),
        "profit_margin":    _safe_float(info.get("profitMargins")),
        # leverage / health
        "debt_to_equity":   _safe_float(info.get("debtToEquity")),
        "current_ratio":    _safe_float(info.get("currentRatio")),
        "quick_ratio":      _safe_float(info.get("quickRatio")),
        # growth
        "revenue_growth":   _safe_float(info.get("revenueGrowth")),
        "earnings_growth":  _safe_float(info.get("earningsGrowth")),
        "earnings_qtr_growth": _safe_float(info.get("earningsQuarterlyGrowth")),
        # price stats
        "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low":  _safe_float(info.get("fiftyTwoWeekLow")),
        "beta":                _safe_float(info.get("beta")),
        # ownership
        "promoter_held": _safe_float(info.get("heldPercentInsiders")),
        "institutions":  _safe_float(info.get("heldPercentInstitutions")),
    }
    return fund


# ---------------------------------------------------------------------------
# public entry point

def fetch_fundamentals(yf_symbol: str) -> dict[str, Any]:
    """Return {ok, error, upcoming_events, fundamentals} for a yfinance symbol."""
    out: dict[str, Any] = {
        "ok": False, "error": None,
        "upcoming_events": [],
        "fundamentals": {},
    }
    if not _YF_AVAILABLE:
        out["error"] = "yfinance not installed"
        return out

    cache_key = f"fundamentals_{yf_symbol}"
    cached = cache.get("fundamentals", cache_key, ttl_seconds=60 * 60 * 6)  # 6h
    if cached is not None:
        return cached

    try:
        import yfinance as yf

        tk = yf.Ticker(yf_symbol)
        try:
            info = tk.info or {}
        except Exception as e:
            log.warning("Ticker.info failed for %s: %s", yf_symbol, e)
            info = {}

        events: list[dict[str, Any]] = []
        events += _earnings_events_from_calendar(tk)
        events += _dividend_events_from_info(info)
        events += _split_events_from_info(info)
        # sort upcoming first, then most recent past
        events.sort(key=lambda e: (
            0 if (e.get("days_until") is not None and e["days_until"] >= 0) else 1,
            abs(e.get("days_until") or 9999),
        ))

        fundamentals = _fundamentals_from_info(info)

        out["ok"] = True
        out["upcoming_events"] = events
        out["fundamentals"] = fundamentals
        cache.set("fundamentals", cache_key, out)
        return out
    except Exception as e:
        log.error("fetch_fundamentals failed for %s: %s", yf_symbol, e)
        out["error"] = str(e)
        return out
