"""Tests for deterministic indicator computation."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.analysis.indicators import (
    atr,
    bollinger,
    compute_indicators,
    macd,
    rsi,
    sma,
    volume_trend_label,
)


def _synthetic_ohlcv(n: int = 260, start: float = 100.0, drift: float = 0.05, seed: int = 42):
    rng = np.random.default_rng(seed)
    closes = [start]
    for _ in range(n - 1):
        shock = rng.normal(0, 1.0)
        closes.append(max(1.0, closes[-1] + drift + shock * 0.5))
    records = []
    for i, c in enumerate(closes):
        records.append({
            "Date": f"2024-01-{i+1:03d}",
            "Open": c * 0.995,
            "High": c * 1.01,
            "Low": c * 0.985,
            "Close": c,
            "Volume": 1_000_000 + int(rng.integers(-50_000, 50_000)),
        })
    return records


def test_sma_matches_rolling_mean():
    s = pd.Series([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    got = sma(s, 3).dropna().tolist()
    expected = s.rolling(3).mean().dropna().tolist()
    assert got == expected


def test_rsi_bounded_0_100():
    s = pd.Series(np.linspace(100, 120, 60))
    r = rsi(s, 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()
    # Pure uptrend should give RSI > 70
    assert r.iloc[-1] > 70


def test_macd_signal_lagging():
    s = pd.Series(np.linspace(100, 200, 100))
    macd_line, signal_line, hist = macd(s)
    assert len(macd_line) == len(s)
    assert len(signal_line) == len(s)
    # On a strong uptrend, MACD line should exceed signal line by the end
    assert macd_line.iloc[-1] > signal_line.iloc[-1]
    assert math.isclose(hist.iloc[-1], macd_line.iloc[-1] - signal_line.iloc[-1], rel_tol=1e-6)


def test_bollinger_widths_positive():
    s = pd.Series(np.random.default_rng(0).normal(100, 2, 60))
    upper, mid, lower = bollinger(s, 20, 2.0)
    tail = pd.concat([upper, mid, lower], axis=1).dropna()
    assert (tail.iloc[:, 0] >= tail.iloc[:, 1]).all()
    assert (tail.iloc[:, 1] >= tail.iloc[:, 2]).all()


def test_atr_positive_values():
    records = _synthetic_ohlcv(60)
    df = pd.DataFrame(records)
    a = atr(df, 14).dropna()
    assert len(a) > 0
    assert (a > 0).all()


def test_volume_trend_label_rising():
    # Build volume where recent > prior by a lot
    v = pd.Series([100] * 20 + [300] * 20)
    assert volume_trend_label(v, window=20) == "rising"


def test_volume_trend_label_flat():
    v = pd.Series([100] * 40)
    assert volume_trend_label(v, window=20) == "flat"


def test_compute_indicators_full_snapshot():
    recs = _synthetic_ohlcv(260)
    snap = compute_indicators(recs)
    assert snap.last_close is not None
    assert snap.sma20 is not None
    assert snap.sma50 is not None
    assert snap.sma200 is not None
    assert snap.rsi14 is not None
    assert snap.macd is not None
    assert snap.bb_upper is not None and snap.bb_lower is not None
    assert snap.atr14 is not None
    assert snap.volume_trend in {"rising", "falling", "flat", None}


def test_compute_indicators_handles_empty():
    snap = compute_indicators([])
    assert snap.last_close is None
    assert snap.sma20 is None
