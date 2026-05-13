"""Deterministic risk rules — flags elevated risk conditions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.output import IndicatorSnapshot, RiskFlags, SentimentSummary, TrendLabel


def _most_recent_age_days(headlines: list[dict[str, Any]]) -> float | None:
    if not headlines:
        return None
    now = datetime.now(timezone.utc)
    ages = []
    for h in headlines:
        pub = h.get("published")
        if not pub:
            continue
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages.append((now - dt).total_seconds() / 86400.0)
        except Exception:
            continue
    return min(ages) if ages else None


def evaluate_risks(
    snap: IndicatorSnapshot,
    trend: TrendLabel,
    sentiment: SentimentSummary,
    headlines: list[dict[str, Any]],
    price_summary: dict[str, Any],
) -> RiskFlags:
    flags = RiskFlags()
    details: list[str] = []

    # Elevated volatility: ATR > 3% of price
    if snap.atr14 and snap.last_close and snap.last_close > 0:
        atr_pct = snap.atr14 / snap.last_close * 100.0
        if atr_pct > 3.0:
            flags.elevated_volatility = True
            details.append(f"ATR14 is {atr_pct:.2f}% of price (>3% threshold)")

    # Bearish momentum
    bearish_signals = 0
    if trend == "downtrend":
        bearish_signals += 1
    if snap.rsi14 is not None and snap.rsi14 < 40:
        bearish_signals += 1
    if snap.macd_hist is not None and snap.macd_hist < 0:
        bearish_signals += 1
    if bearish_signals >= 2:
        flags.bearish_momentum = True
        details.append(f"{bearish_signals}/3 momentum signals are bearish")

    # Conflicting signals: trend vs sentiment disagree strongly
    if trend == "uptrend" and sentiment.label == "bearish":
        flags.conflicting_signals = True
        details.append("Uptrend price action conflicts with bearish sentiment")
    elif trend == "downtrend" and sentiment.label == "bullish":
        flags.conflicting_signals = True
        details.append("Downtrend price action conflicts with bullish sentiment")

    # Weak coverage
    n_sources = len(headlines) + sentiment.n_articles + sentiment.n_transcripts
    if n_sources < 3:
        flags.weak_coverage = True
        details.append(f"Only {n_sources} content sources available")

    # Stale data
    age = _most_recent_age_days(headlines)
    if age is not None and age > 7:
        flags.stale_data = True
        details.append(f"Most recent headline is {age:.1f} days old")
    elif age is None and not headlines:
        flags.stale_data = True
        details.append("No dated news available")

    flags.details = details
    return flags
