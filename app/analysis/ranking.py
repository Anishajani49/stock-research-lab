"""Evidence ranking — ticker relevance + recency + importance.

Takes a list of DevelopmentEvents (deterministic, already tagged) and sorts
them so the LLM prompt sees the MOST ticker-specific, recent, high-importance
items first — which is the single biggest lever on output quality.
"""

from __future__ import annotations

import math
from typing import Iterable

from app.schemas.output import DevelopmentEvent


# Weights (deliberately simple — readable + tweakable)
W_TICKER       = 1.8     # how directly the item mentions the ticker/company
W_IMPORTANCE   = 1.0     # category severity, 1..5
W_RECENCY      = 1.2     # newer = more useful
W_POLARITY     = 0.3     # slight boost for non-neutral items (they drive decisions)
HALF_LIFE_DAYS = 10.0    # recency decays with this half-life


def _recency_score(age_days: float | None) -> float:
    """Return 0..1. 0 days → 1.0, half-life → 0.5, old → approaches 0."""
    if age_days is None:
        return 0.4   # unknown date — assume medium freshness
    if age_days < 0:
        age_days = 0.0
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


def rank_events(
    events: Iterable[DevelopmentEvent],
    top_k: int | None = None,
    min_ticker_match: float = 0.0,
) -> list[DevelopmentEvent]:
    """Return events sorted best-first.

    If min_ticker_match > 0, events below that threshold are dropped entirely —
    useful when evidence is crowded with generic macro news.
    """
    ranked: list[tuple[float, DevelopmentEvent]] = []
    for ev in events:
        if ev.ticker_match < min_ticker_match:
            continue
        score = (
            W_TICKER * ev.ticker_match
            + W_IMPORTANCE * (ev.importance / 5.0)
            + W_RECENCY * _recency_score(ev.age_days)
            + (W_POLARITY if ev.polarity != "neutral" else 0.0)
        )
        ranked.append((score, ev))

    ranked.sort(key=lambda t: t[0], reverse=True)
    out = [ev for _, ev in ranked]
    if top_k is not None:
        out = out[:top_k]
    return out


def split_by_polarity(events: Iterable[DevelopmentEvent]) -> tuple[list[DevelopmentEvent], list[DevelopmentEvent], list[DevelopmentEvent]]:
    """Split into (bullish, bearish, neutral) keeping input order."""
    bull, bear, neut = [], [], []
    for ev in events:
        if ev.polarity == "bullish":
            bull.append(ev)
        elif ev.polarity == "bearish":
            bear.append(ev)
        else:
            neut.append(ev)
    return bull, bear, neut
