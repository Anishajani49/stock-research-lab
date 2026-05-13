"""Candlestick pattern detector — operates on plain OHLCV dicts.

Rules are textbook-style (Bulkowski / Nison heuristics) and deliberately
lenient — we want the teacher module to have SOMETHING to point at on
real charts, even if patterns aren't picture-perfect. Confidence scores
reflect how close to the textbook shape the match was.

Each bar is expected to be a dict with keys:
    Date / Open / High / Low / Close / Volume
(the case used by yfinance via the market adapter).
"""

from __future__ import annotations

from typing import Any

from app.schemas.output import CandleDetection


# ---------------------------------------------------------------------------
# Helpers

def _b(bar: dict[str, Any]) -> tuple[float, float, float, float, str]:
    """Return (open, high, low, close, date_str)."""
    o = float(bar.get("Open") or 0.0)
    h = float(bar.get("High") or 0.0)
    l = float(bar.get("Low") or 0.0)
    c = float(bar.get("Close") or 0.0)
    d = str(bar.get("Date") or "")
    return o, h, l, c, d


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(1e-9, h - l)


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


def _upper_wick(o: float, h: float, c: float) -> float:
    return h - max(o, c)


def _lower_wick(o: float, l: float, c: float) -> float:
    return min(o, c) - l


def _trend_before(bars: list[dict[str, Any]], idx: int, lookback: int = 5) -> str:
    """Very lightweight trend detector over the last `lookback` bars ending at idx-1."""
    if idx <= 0:
        return "unclear"
    start = max(0, idx - lookback)
    window = bars[start:idx]
    if len(window) < 3:
        return "unclear"
    closes = [float(b.get("Close") or 0.0) for b in window]
    if closes[-1] > closes[0] * 1.02:
        return "uptrend"
    if closes[-1] < closes[0] * 0.98:
        return "downtrend"
    return "sideways"


# ---------------------------------------------------------------------------
# Single-candle detections

def _detect_doji(bar: dict[str, Any], idx: int) -> CandleDetection | None:
    o, h, l, c, d = _b(bar)
    rng = _range(h, l)
    body = _body(o, c)
    if rng <= 0:
        return None
    if body / rng <= 0.1:
        conf = 1.0 - (body / rng) * 5.0
        return CandleDetection(
            pattern="doji", index=idx, date=d, bias="neutral",
            confidence=round(max(0.3, min(1.0, conf)), 2),
            note="Open and close were nearly equal — the period ended in indecision.",
        )
    return None


def _detect_hammer(bar: dict[str, Any], idx: int, trend: str) -> CandleDetection | None:
    o, h, l, c, d = _b(bar)
    rng = _range(h, l)
    body = _body(o, c)
    upper = _upper_wick(o, h, c)
    lower = _lower_wick(o, l, c)
    if body <= 0:
        return None
    if lower >= 2.0 * body and upper <= 0.3 * lower and body / rng < 0.4:
        base_conf = min(1.0, lower / (body * 3.0))
        # stronger signal after a downtrend
        conf = base_conf * (1.1 if trend == "downtrend" else 0.6)
        return CandleDetection(
            pattern="hammer", index=idx, date=d, bias="bullish",
            confidence=round(min(1.0, conf), 2),
            note=(
                "Long lower wick: sellers pushed the price down, then buyers pushed it "
                "back near the open. " + (
                    "Appeared after a downtrend — classic setup."
                    if trend == "downtrend" else
                    "Context is not a clean downtrend, so treat it with extra caution."
                )
            ),
        )
    return None


def _detect_shooting_star(bar: dict[str, Any], idx: int, trend: str) -> CandleDetection | None:
    o, h, l, c, d = _b(bar)
    rng = _range(h, l)
    body = _body(o, c)
    upper = _upper_wick(o, h, c)
    lower = _lower_wick(o, l, c)
    if body <= 0:
        return None
    if upper >= 2.0 * body and lower <= 0.3 * upper and body / rng < 0.4:
        base_conf = min(1.0, upper / (body * 3.0))
        conf = base_conf * (1.1 if trend == "uptrend" else 0.6)
        return CandleDetection(
            pattern="shooting_star", index=idx, date=d, bias="bearish",
            confidence=round(min(1.0, conf), 2),
            note=(
                "Long upper wick: buyers pushed the price up, then sellers drove it "
                "back down. " + (
                    "Appeared after an uptrend — classic topping signal."
                    if trend == "uptrend" else
                    "Context is not a clean uptrend, so treat it with extra caution."
                )
            ),
        )
    return None


def _detect_marubozu(bar: dict[str, Any], idx: int) -> CandleDetection | None:
    o, h, l, c, d = _b(bar)
    rng = _range(h, l)
    body = _body(o, c)
    upper = _upper_wick(o, h, c)
    lower = _lower_wick(o, l, c)
    if body / rng < 0.9:
        return None
    if upper + lower > 0.1 * rng:
        return None
    if _is_bullish(o, c):
        return CandleDetection(
            pattern="marubozu_bullish", index=idx, date=d, bias="bullish",
            confidence=round(body / rng, 2),
            note="Full-body bullish candle — buyers controlled the entire period.",
        )
    if _is_bearish(o, c):
        return CandleDetection(
            pattern="marubozu_bearish", index=idx, date=d, bias="bearish",
            confidence=round(body / rng, 2),
            note="Full-body bearish candle — sellers controlled the entire period.",
        )
    return None


# ---------------------------------------------------------------------------
# Multi-candle detections

def _detect_engulfing(bars: list[dict[str, Any]], idx: int, trend: str) -> CandleDetection | None:
    if idx < 1:
        return None
    p_o, p_h, p_l, p_c, _ = _b(bars[idx - 1])
    o, h, l, c, d = _b(bars[idx])
    prev_body = _body(p_o, p_c)
    cur_body = _body(o, c)
    if prev_body == 0 or cur_body < prev_body:
        return None

    # Bullish engulfing: prev bearish, current bullish, body swallows
    if _is_bearish(p_o, p_c) and _is_bullish(o, c):
        if o <= p_c and c >= p_o:
            conf = min(1.0, cur_body / (prev_body + 1e-9) - 1.0 + 0.6)
            conf *= 1.1 if trend == "downtrend" else 0.7
            return CandleDetection(
                pattern="bullish_engulfing", index=idx, date=d, bias="bullish",
                confidence=round(min(1.0, conf), 2),
                note="Today's green body fully swallowed yesterday's red body — buyers took over.",
            )
    # Bearish engulfing
    if _is_bullish(p_o, p_c) and _is_bearish(o, c):
        if o >= p_c and c <= p_o:
            conf = min(1.0, cur_body / (prev_body + 1e-9) - 1.0 + 0.6)
            conf *= 1.1 if trend == "uptrend" else 0.7
            return CandleDetection(
                pattern="bearish_engulfing", index=idx, date=d, bias="bearish",
                confidence=round(min(1.0, conf), 2),
                note="Today's red body fully swallowed yesterday's green body — sellers took over.",
            )
    return None


def _detect_harami(bars: list[dict[str, Any]], idx: int, trend: str) -> CandleDetection | None:
    if idx < 1:
        return None
    p_o, _, _, p_c, _ = _b(bars[idx - 1])
    o, _, _, c, d = _b(bars[idx])
    prev_body = _body(p_o, p_c)
    cur_body = _body(o, c)
    if prev_body == 0 or cur_body >= prev_body:
        return None
    # current body inside previous body
    prev_top = max(p_o, p_c)
    prev_bot = min(p_o, p_c)
    cur_top = max(o, c)
    cur_bot = min(o, c)
    if cur_top > prev_top or cur_bot < prev_bot:
        return None

    if _is_bearish(p_o, p_c) and _is_bullish(o, c):
        conf = 0.6 if trend == "downtrend" else 0.4
        return CandleDetection(
            pattern="bullish_harami", index=idx, date=d, bias="bullish",
            confidence=conf,
            note="Small bullish candle nested inside yesterday's bigger bearish candle — selling paused.",
        )
    if _is_bullish(p_o, p_c) and _is_bearish(o, c):
        conf = 0.6 if trend == "uptrend" else 0.4
        return CandleDetection(
            pattern="bearish_harami", index=idx, date=d, bias="bearish",
            confidence=conf,
            note="Small bearish candle nested inside yesterday's bigger bullish candle — buying paused.",
        )
    return None


def _detect_star(bars: list[dict[str, Any]], idx: int, trend: str) -> CandleDetection | None:
    if idx < 2:
        return None
    a_o, _, _, a_c, _ = _b(bars[idx - 2])
    b_o, _, _, b_c, _ = _b(bars[idx - 1])
    c_o, _, _, c_c, d = _b(bars[idx])
    a_body = _body(a_o, a_c)
    b_body = _body(b_o, b_c)
    c_body = _body(c_o, c_c)
    if a_body == 0 or c_body == 0:
        return None
    # 1st and 3rd must be larger-bodied than the middle "star"
    if b_body > 0.5 * a_body or b_body > 0.5 * c_body:
        return None
    # Morning star: bearish, small, bullish closing well into first body
    if _is_bearish(a_o, a_c) and _is_bullish(c_o, c_c) and c_c > (a_o + a_c) / 2:
        conf = 0.8 if trend == "downtrend" else 0.5
        return CandleDetection(
            pattern="morning_star", index=idx, date=d, bias="bullish",
            confidence=conf,
            note="Three-bar reversal: big red → small indecision → big green closing into the first red.",
        )
    # Evening star
    if _is_bullish(a_o, a_c) and _is_bearish(c_o, c_c) and c_c < (a_o + a_c) / 2:
        conf = 0.8 if trend == "uptrend" else 0.5
        return CandleDetection(
            pattern="evening_star", index=idx, date=d, bias="bearish",
            confidence=conf,
            note="Three-bar topping: big green → small indecision → big red closing into the first green.",
        )
    return None


# ---------------------------------------------------------------------------
# Public API

def detect_all(ohlcv: list[dict[str, Any]], max_per_pattern: int = 2) -> list[CandleDetection]:
    """Scan OHLCV and return detections. Limited per pattern so the lesson
    stays readable for beginners."""
    if not ohlcv:
        return []
    found: list[CandleDetection] = []
    counts: dict[str, int] = {}

    def _keep(det: CandleDetection | None) -> None:
        if det is None:
            return
        if counts.get(det.pattern, 0) >= max_per_pattern:
            return
        found.append(det)
        counts[det.pattern] = counts.get(det.pattern, 0) + 1

    # Walk recent bars (most recent last). Iterate newest first so recent
    # examples bubble up, then sort later.
    n = len(ohlcv)
    for i in range(n - 1, -1, -1):
        trend = _trend_before(ohlcv, i)
        bar = ohlcv[i]

        _keep(_detect_doji(bar, i))
        _keep(_detect_hammer(bar, i, trend))
        _keep(_detect_shooting_star(bar, i, trend))
        _keep(_detect_marubozu(bar, i))
        _keep(_detect_engulfing(ohlcv, i, trend))
        _keep(_detect_harami(ohlcv, i, trend))
        _keep(_detect_star(ohlcv, i, trend))

    # Sort newest → oldest in output
    found.sort(key=lambda d: d.index, reverse=True)
    return found
