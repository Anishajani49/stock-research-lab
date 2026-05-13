"""Deterministic technical indicator computation.

Pure pandas/numpy implementations to avoid a hard dependency on pandas-ta
(and to ensure reproducibility on Apple Silicon).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.schemas.output import IndicatorSnapshot


def _to_close_series(ohlcv: list[dict[str, Any]]) -> pd.DataFrame:
    if not ohlcv:
        return pd.DataFrame()
    df = pd.DataFrame(ohlcv)
    for c in ("Open", "High", "Low", "Close", "Volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    # Avoid div-by-zero: when avg_loss is 0 and avg_gain > 0, RSI should be 100
    # (pure uptrend). Using NaN here would drop those rows during .dropna().
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    rsi_val = rsi_val.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return rsi_val


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(series: pd.Series, window: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(window=window, min_periods=window).mean()
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + k * std
    lower = mid - k * std
    return upper, mid, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if not {"High", "Low", "Close"}.issubset(df.columns):
        return pd.Series(dtype=float)
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def volume_trend_label(volume: pd.Series, window: int = 20) -> str | None:
    if volume is None or volume.empty or len(volume) < window + 5:
        return None
    recent = volume.tail(window).mean()
    prior = volume.iloc[-2 * window:-window].mean() if len(volume) >= 2 * window else volume.head(window).mean()
    if not np.isfinite(recent) or not np.isfinite(prior) or prior == 0:
        return None
    change = (recent - prior) / prior
    if change > 0.10:
        return "rising"
    if change < -0.10:
        return "falling"
    return "flat"


def _last_or_none(s: pd.Series) -> float | None:
    if s is None or s.empty:
        return None
    v = s.iloc[-1]
    if pd.isna(v):
        return None
    return float(v)


def compute_indicators(ohlcv: list[dict[str, Any]]) -> IndicatorSnapshot:
    """Compute a snapshot of indicators from OHLCV records."""
    snap = IndicatorSnapshot()
    df = _to_close_series(ohlcv)
    if df.empty or "Close" not in df.columns:
        return snap

    close = df["Close"].astype(float)

    snap.last_close = _last_or_none(close)
    snap.sma20 = _last_or_none(sma(close, 20))
    snap.sma50 = _last_or_none(sma(close, 50))
    snap.sma200 = _last_or_none(sma(close, 200))
    snap.rsi14 = _last_or_none(rsi(close, 14))

    macd_line, signal_line, hist = macd(close)
    snap.macd = _last_or_none(macd_line)
    snap.macd_signal = _last_or_none(signal_line)
    snap.macd_hist = _last_or_none(hist)

    upper, mid, lower = bollinger(close)
    snap.bb_upper = _last_or_none(upper)
    snap.bb_mid = _last_or_none(mid)
    snap.bb_lower = _last_or_none(lower)

    snap.atr14 = _last_or_none(atr(df, 14))
    if "Volume" in df.columns:
        snap.volume_trend = volume_trend_label(df["Volume"].astype(float))

    return snap
