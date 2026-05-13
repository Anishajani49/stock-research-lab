"""Candlestick Learning Mode — beginner-first, deterministic, LLM-free.

This package is deliberately isolated from the stock analysis pipeline.
It exports:

    build_lesson(ticker: str | None, ohlcv: list[dict] | None) -> LearningLesson

which returns a structured lesson covering:
  - candle anatomy
  - bullish vs bearish candles
  - single-candle patterns (doji, hammer, shooting star, marubozu)
  - multi-candle patterns (engulfing, morning star, evening star, harami)
  - confirmation logic + why context, volume, and support/resistance matter
  - real detections on the supplied OHLCV (if provided)
"""

from app.learn.lesson import build_lesson  # noqa: F401
