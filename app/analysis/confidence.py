"""Confidence scoring.

Combines:
- data completeness (market + news + indicators available)
- source freshness
- source agreement (sentiment vs trend)
- indicator alignment (SMA stack consistency, RSI extremes)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.output import ConfidenceLabel, IndicatorSnapshot, SentimentSummary, TrendLabel


def _freshness_score(headlines: list[dict[str, Any]]) -> float:
    """1.0 if we have recent (<3d) headlines, degrades with age."""
    if not headlines:
        return 0.0
    now = datetime.now(timezone.utc)
    ages_days = []
    for h in headlines:
        pub = h.get("published")
        if not pub:
            continue
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_days.append((now - dt).total_seconds() / 86400.0)
        except Exception:
            continue
    if not ages_days:
        return 0.4  # some headlines but no parseable dates
    min_age = min(ages_days)
    if min_age < 1:
        return 1.0
    if min_age < 3:
        return 0.8
    if min_age < 7:
        return 0.6
    if min_age < 14:
        return 0.3
    return 0.1


def _alignment_score(snap: IndicatorSnapshot, trend: TrendLabel, sentiment: SentimentSummary) -> float:
    score = 0.5
    if trend in ("uptrend", "downtrend") and sentiment.label in ("bullish", "bearish"):
        aligned = (trend == "uptrend" and sentiment.label == "bullish") or (
            trend == "downtrend" and sentiment.label == "bearish"
        )
        score = 1.0 if aligned else 0.2

    # Indicator internal consistency
    if snap.sma20 and snap.sma50:
        stack_up = snap.last_close and snap.last_close > snap.sma20 > snap.sma50
        stack_down = snap.last_close and snap.last_close < snap.sma20 < snap.sma50
        if trend == "uptrend" and stack_up:
            score = min(1.0, score + 0.1)
        elif trend == "downtrend" and stack_down:
            score = min(1.0, score + 0.1)
    return score


def _completeness_score(state_flags: dict[str, bool]) -> float:
    """state_flags includes keys: market, indicators, news, articles."""
    weights = {"market": 0.45, "indicators": 0.3, "news": 0.15, "articles": 0.1}
    return sum(w for k, w in weights.items() if state_flags.get(k))


def score_confidence(
    snap: IndicatorSnapshot,
    trend: TrendLabel,
    sentiment: SentimentSummary,
    headlines: list[dict[str, Any]],
    flags: dict[str, bool],
) -> tuple[ConfidenceLabel, float]:
    comp = _completeness_score(flags)
    fresh = _freshness_score(headlines)
    align = _alignment_score(snap, trend, sentiment)
    raw = 0.45 * comp + 0.25 * fresh + 0.30 * align
    raw = max(0.0, min(1.0, raw))
    if raw >= 0.70:
        return "High", round(raw, 3)
    if raw >= 0.45:
        return "Medium", round(raw, 3)
    return "Low", round(raw, 3)
