"""Trend classification — uptrend / downtrend / sideways / unclear."""

from __future__ import annotations

from app.schemas.output import IndicatorSnapshot, TrendLabel


def classify_trend(snap: IndicatorSnapshot) -> TrendLabel:
    """Simple, explainable trend classifier based on SMA stack + price position.

    - Uptrend: close > SMA20 > SMA50 (SMA200 confirming if available)
    - Downtrend: close < SMA20 < SMA50 (SMA200 confirming if available)
    - Sideways: SMAs close together and no clear ordering
    - Unclear: insufficient data
    """
    c, s20, s50, s200 = snap.last_close, snap.sma20, snap.sma50, snap.sma200
    if None in (c, s20, s50):
        return "unclear"

    spread = max(abs(s20 - s50), 1e-9) / max(abs(c), 1e-9)

    if c > s20 > s50 and (s200 is None or s50 >= s200 * 0.98):
        return "uptrend"
    if c < s20 < s50 and (s200 is None or s50 <= s200 * 1.02):
        return "downtrend"
    if spread < 0.01:
        return "sideways"
    return "unclear"
