"""Lightweight lexicon-based sentiment engine.

Deterministic (no LLM) — computes weighted sentiment from headlines, articles,
and transcripts using a small finance-tuned lexicon.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.output import SentimentSummary


POSITIVE = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies",
    "gain", "gains", "record", "upgrade", "upgrades", "outperform",
    "strong", "robust", "buy", "bullish", "profit", "profits",
    "growth", "rising", "rises", "boost", "boosts", "tops", "top",
    "breakthrough", "expands", "partnership", "accelerates",
}
NEGATIVE = {
    "miss", "misses", "plunge", "plunges", "slump", "slumps",
    "loss", "losses", "downgrade", "downgrades", "underperform",
    "weak", "sell", "bearish", "decline", "declines", "falling",
    "falls", "drop", "drops", "cuts", "cut", "warns", "warning",
    "lawsuit", "probe", "investigation", "recall", "fraud",
    "layoffs", "layoff", "bankruptcy", "defaults", "risk",
}

NEGATORS = {"not", "no", "never", "without", "hardly", "barely"}

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _score_text(text: str) -> tuple[float, int, int]:
    """Return (score, pos_hits, neg_hits) in [-1, 1]."""
    if not text:
        return 0.0, 0, 0
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    pos = neg = 0
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else ""
        flip = prev in NEGATORS
        if tok in POSITIVE:
            neg += 1 if flip else 0
            pos += 0 if flip else 1
        elif tok in NEGATIVE:
            pos += 1 if flip else 0
            neg += 0 if flip else 1
    total = pos + neg
    if total == 0:
        return 0.0, 0, 0
    score = (pos - neg) / total
    return score, pos, neg


def _label_from_score(score: float, total_hits: int, n_sources: int) -> str:
    if n_sources == 0 or total_hits == 0:
        return "insufficient"
    if score > 0.25:
        return "bullish"
    if score < -0.25:
        return "bearish"
    if -0.25 <= score <= 0.25 and total_hits >= 4:
        return "neutral"
    return "mixed"


def compute_sentiment(
    headlines: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    transcripts: list[dict[str, Any]],
) -> SentimentSummary:
    """Weighted: headlines x1, articles x2, transcripts x2."""
    weighted_sum = 0.0
    weight_total = 0.0
    total_pos = total_neg = 0

    for h in headlines:
        text = (h.get("title") or "") + " " + (h.get("snippet") or "")
        s, p, n = _score_text(text)
        if p + n > 0:
            weighted_sum += s * 1.0
            weight_total += 1.0
            total_pos += p
            total_neg += n

    for a in articles:
        if not a.get("ok"):
            continue
        text = (a.get("title") or "") + " " + (a.get("text") or "")
        s, p, n = _score_text(text[:4000])
        if p + n > 0:
            weighted_sum += s * 2.0
            weight_total += 2.0
            total_pos += p
            total_neg += n

    for t in transcripts:
        if not t.get("ok"):
            continue
        text = t.get("text") or ""
        s, p, n = _score_text(text[:4000])
        if p + n > 0:
            weighted_sum += s * 2.0
            weight_total += 2.0
            total_pos += p
            total_neg += n

    score = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    total_hits = total_pos + total_neg
    n_sources = len(headlines) + sum(1 for a in articles if a.get("ok")) + sum(1 for t in transcripts if t.get("ok"))
    label = _label_from_score(score, total_hits, n_sources)

    notes = f"pos={total_pos} neg={total_neg} over {n_sources} sources"
    return SentimentSummary(
        score=round(score, 3),
        label=label,  # type: ignore[arg-type]
        n_headlines=len(headlines),
        n_articles=sum(1 for a in articles if a.get("ok")),
        n_transcripts=sum(1 for t in transcripts if t.get("ok")),
        notes=notes,
    )
