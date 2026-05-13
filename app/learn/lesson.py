"""Build a beginner-friendly candlestick lesson.

Deterministic — no LLM needed. If the caller passes OHLCV we enrich the
lesson with real detections so the beginner can see textbook patterns on
actual charts.
"""

from __future__ import annotations

from typing import Any

from app.learn.detector import detect_all
from app.learn.patterns import (
    ANATOMY,
    BULLISH_VS_BEARISH,
    CONTEXT_NOTES,
    PATTERN_CATALOG,
    get_pattern,
)
from app.schemas.output import LearningLesson


def _section_anatomy() -> dict[str, Any]:
    return {"type": "anatomy", **ANATOMY}


def _section_bullish_vs_bearish() -> dict[str, Any]:
    return {"type": "bullish_vs_bearish", **BULLISH_VS_BEARISH}


def _section_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "pattern",
        "name": pattern["name"],
        "display": pattern["display"],
        "pattern_type": pattern["type"],
        "bias": pattern["bias"],
        "what_it_is": pattern["what_it_is"],
        "what_it_may_suggest": pattern["what_it_may_suggest"],
        "when_it_matters": pattern["when_it_matters"],
        "when_it_fails": pattern["when_it_fails"],
        "confirmation": pattern["confirmation"],
        "example_ascii": pattern["example_ascii"],
    }


def _section_context() -> dict[str, Any]:
    return {"type": "context", **CONTEXT_NOTES}


def _summarize_chart(
    ohlcv: list[dict[str, Any]],
    detections: list[Any],
    ticker: str | None,
    company_name: str | None,
    timeframe: str | None,
) -> str:
    """Plain-English, deterministic chart narration for beginners.
    No LLM — just what the numbers say.
    """
    if not ohlcv:
        return ""
    try:
        closes = [float(b.get("Close") or 0.0) for b in ohlcv]
        highs = [float(b.get("High") or 0.0) for b in ohlcv]
        lows = [float(b.get("Low") or 0.0) for b in ohlcv]
        vols = [float(b.get("Volume") or 0.0) for b in ohlcv]
    except Exception:
        return ""
    if not closes:
        return ""

    first = closes[0]
    last = closes[-1]
    if first <= 0:
        return ""
    pct = (last - first) / first * 100.0

    # Trend bucket
    if pct > 5:
        trend = "a net uptrend"
    elif pct < -5:
        trend = "a net downtrend"
    else:
        trend = "a sideways / range-bound period"

    hi = max(highs) if highs else last
    lo = min(lows) if lows else last
    hi_idx = highs.index(hi) if highs else -1
    lo_idx = lows.index(lo) if lows else -1

    # Position of last close within the period range
    if hi > lo:
        pos = (last - lo) / (hi - lo)
        if pos > 0.8:
            position = "near the top of the range"
        elif pos < 0.2:
            position = "near the bottom of the range"
        else:
            position = "somewhere in the middle of the range"
    else:
        position = "inside a very tight range"

    # Volume drift: compare last quarter vs prior quarter
    vol_note = ""
    if len(vols) >= 8 and sum(vols) > 0:
        q = max(4, len(vols) // 4)
        recent = sum(vols[-q:]) / q
        prior = sum(vols[-2 * q:-q]) / q if len(vols) >= 2 * q else sum(vols[:-q]) / max(1, len(vols) - q)
        if prior > 0:
            v_pct = (recent - prior) / prior * 100.0
            if v_pct > 20:
                vol_note = "Volume has been rising lately — more people trading than before."
            elif v_pct < -20:
                vol_note = "Volume has been fading — interest has cooled."
            else:
                vol_note = "Volume looks roughly steady across the window."

    # Detections summary
    det_note = ""
    if detections:
        by_bias: dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0}
        for d in detections:
            by_bias[d.bias] = by_bias.get(d.bias, 0) + 1
        det_note = (
            f"I spotted {len(detections)} textbook-ish pattern(s) in this window — "
            f"{by_bias.get('bullish', 0)} bullish, {by_bias.get('bearish', 0)} bearish, "
            f"{by_bias.get('neutral', 0)} neutral. Each one is marked on the chart; "
            "click a row in the detections table to see what it means."
        )
    else:
        det_note = (
            "No textbook-grade patterns jumped out in this window — real charts are "
            "messy, and that's fine. Try a longer timeframe to see more examples."
        )

    name = company_name or ticker or "this instrument"
    tf = timeframe or "the selected window"
    bits = [
        f"Over the last {tf}, {name} shows **{trend}** — price moved from "
        f"{first:.2f} to {last:.2f} ({pct:+.1f}%).",
        f"High of the period was {hi:.2f} and the low was {lo:.2f}. "
        f"The last close sits **{position}**.",
    ]
    if vol_note:
        bits.append(vol_note)
    bits.append(det_note)
    bits.append(
        "Remember: this is a learning view — we're pointing at candlestick shapes, "
        "not telling you what to do. For a full research view, use the Stock Analysis tab."
    )
    # Silence unused indices warning (kept for future markers)
    _ = (hi_idx, lo_idx)
    return "\n\n".join(bits)


def build_lesson(
    ticker: str | None = None,
    ohlcv: list[dict[str, Any]] | None = None,
    company_name: str | None = None,
    timeframe: str | None = None,
) -> LearningLesson:
    """Return a structured lesson. OHLCV is optional — used only to highlight
    real detections for the beginner."""
    sections: list[dict[str, Any]] = []
    sections.append(_section_anatomy())
    sections.append(_section_bullish_vs_bearish())

    # Single-candle, then multi-candle
    for p in PATTERN_CATALOG:
        if p["type"] == "single":
            sections.append(_section_pattern(p))
    for p in PATTERN_CATALOG:
        if p["type"] == "multi":
            sections.append(_section_pattern(p))

    sections.append(_section_context())

    detections = detect_all(ohlcv or [])

    # Attach per-pattern example rows from detections
    by_pattern: dict[str, list[dict[str, Any]]] = {}
    for det in detections:
        by_pattern.setdefault(det.pattern, []).append({
            "index": det.index,
            "date": det.date,
            "bias": det.bias,
            "confidence": det.confidence,
            "note": det.note,
        })
    for sec in sections:
        if sec.get("type") == "pattern":
            name = sec.get("name")
            sec["real_examples"] = by_pattern.get(name, [])

    last_close = None
    n_bars = 0
    if ohlcv:
        n_bars = len(ohlcv)
        try:
            last_close = float(ohlcv[-1].get("Close") or 0.0) or None
        except Exception:
            last_close = None

    chart_summary = _summarize_chart(
        ohlcv or [], detections, ticker, company_name, timeframe,
    )

    return LearningLesson(
        ticker=ticker,
        company_name=company_name,
        timeframe=timeframe,
        lesson_sections=sections,
        detections=detections,
        last_close=last_close,
        n_bars=n_bars,
        ohlcv=list(ohlcv or []),
        chart_summary=chart_summary,
    )


# Re-exported for convenience
__all__ = ["build_lesson", "get_pattern"]
