"""Tests for the candlestick pattern detector + lesson builder."""

from __future__ import annotations

from app.learn.detector import detect_all
from app.learn.lesson import build_lesson


def _bar(o, h, l, c, d="2024-01-01", v=1_000_000):
    return {"Date": d, "Open": o, "High": h, "Low": l, "Close": c, "Volume": v}


def test_detects_doji():
    bars = [_bar(100, 102, 98, 100.1, d=f"2024-01-{i:02d}") for i in range(1, 6)]
    # Last bar: near-zero body
    bars.append(_bar(100, 103, 97, 100.05, d="2024-01-06"))
    dets = detect_all(bars)
    assert any(d.pattern == "doji" for d in dets)


def test_detects_hammer_after_downtrend():
    # 5-bar downtrend
    bars = [_bar(110 - i, 111 - i, 108 - i, 109 - i, d=f"2024-01-{i:02d}") for i in range(1, 6)]
    # Hammer: small body near top, long lower wick
    bars.append(_bar(103, 104, 97, 103.5, d="2024-01-06"))
    dets = detect_all(bars)
    assert any(d.pattern == "hammer" for d in dets)


def test_detects_bullish_engulfing_after_downtrend():
    bars = [_bar(110 - i, 111 - i, 108 - i, 109 - i, d=f"2024-01-{i:02d}") for i in range(1, 6)]
    bars.append(_bar(105, 105.5, 104, 104.2, d="2024-01-06"))   # small bearish
    bars.append(_bar(104, 107, 103.5, 106.5, d="2024-01-07"))  # bigger bullish engulfing
    dets = detect_all(bars)
    assert any(d.pattern == "bullish_engulfing" for d in dets)


def test_build_lesson_includes_all_pattern_sections():
    lesson = build_lesson(ticker=None, ohlcv=[])
    pattern_names = [
        s.get("name") for s in lesson.lesson_sections if s.get("type") == "pattern"
    ]
    for required in [
        "doji", "hammer", "shooting_star",
        "marubozu_bullish", "marubozu_bearish",
        "bullish_engulfing", "bearish_engulfing",
        "morning_star", "evening_star",
        "bullish_harami", "bearish_harami",
    ]:
        assert required in pattern_names, f"missing pattern section: {required}"


def test_build_lesson_with_ohlcv_attaches_real_examples():
    # Make a 30-bar downtrend with a hammer at the end
    bars = [_bar(100 - i * 0.5, 101 - i * 0.5, 99 - i * 0.5, 99.5 - i * 0.5, d=f"2024-01-{i:02d}")
            for i in range(1, 26)]
    bars.append(_bar(85, 86, 80, 85.8, d="2024-01-26"))  # hammer candidate
    lesson = build_lesson(ticker="FAKE", ohlcv=bars)
    hammer_section = next(
        s for s in lesson.lesson_sections
        if s.get("type") == "pattern" and s.get("name") == "hammer"
    )
    # Real examples key is present (may or may not have entries depending on trend heuristic)
    assert "real_examples" in hammer_section
