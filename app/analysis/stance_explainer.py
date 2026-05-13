"""Translate the rules-engine stance into a beginner-friendly explanation.

The stance engine already produces `reasons`, `bull_points`, `bear_points`,
and `what_changes_view`. This module wraps those into a structured object
that the UI can render: a beginner takeaway, the technical rules with
plain-English glosses, and a small reference dictionary so the user can see
all five possible leanings at a glance.
"""

from __future__ import annotations

from typing import Any

from app.schemas.output import ResearchState


# ---------------------------------------------------------------------------
# Per-stance beginner take

STANCE_PRETTY: dict[str, str] = {
    "watch":                 "👀 Watch",
    "research_more":         "🔍 Research more",
    "early_positive_setup":  "🟢 Early positive setup",
    "wait_for_confirmation": "🟡 Wait for confirmation",
    "avoid_for_now":         "🔴 Avoid for now",
}


STANCE_HEADLINE: dict[str, str] = {
    "watch":                 "Nothing strong is pushing this stock either way right now.",
    "research_more":         "There isn't enough information to form a confident view.",
    "early_positive_setup":  "Chart + momentum align positively — but it's early, not confirmed.",
    "wait_for_confirmation": "Signals genuinely disagree — the market hasn't decided yet.",
    "avoid_for_now":         "A concrete negative is on the record — the downside is real, the upside is hopeful.",
}


STANCE_BEGINNER_MEANING: dict[str, str] = {
    "watch": (
        "A 'watch' verdict means the rules engine couldn't find strong evidence "
        "in either direction. As a beginner, that's actually a useful signal: there's "
        "no clear story yet. Your job here is to KEEP AN EYE on the stock — wait for "
        "a real catalyst (good or bad earnings, a regulator action, a chart breakout) "
        "before forming a view. No action is itself a valid action."
    ),
    "research_more": (
        "A 'research more' verdict means the data the engine had was too thin to form "
        "a confident view — either news coverage was weak, or the price data didn't come "
        "through, or both. Don't act on what you see here. Read the company's most recent "
        "quarterly result and at least 2–3 named outlets (ET / MoneyControl / Mint) before "
        "forming any opinion."
    ),
    "early_positive_setup": (
        "An 'early positive setup' verdict means the chart and the momentum gauge are "
        "BOTH pointing positive — the price is in an uptrend, holding above its 50-day "
        "average, and MACD is supportive. This is NOT a buy signal. It's a 'the setup "
        "looks healthy, but it's early' note. A beginner should still wait for one more "
        "confirmation (another good quarter, a follow-through up-move on rising volume) "
        "and never put in more than they can afford to lose."
    ),
    "wait_for_confirmation": (
        "A 'wait for confirmation' verdict means the signals are MIXED — one part of the "
        "picture (e.g. price trend) says one thing, another part (e.g. momentum, or news) "
        "says the opposite. The honest answer is: nobody knows yet. Wait for the next "
        "earnings or a clear news catalyst before deciding anything."
    ),
    "avoid_for_now": (
        "An 'avoid for now' verdict means a specific bad event is on the record — a "
        "regulator action, a confirmed downtrend with bearish momentum, or a similar "
        "concrete negative. Until that risk is clearly resolved, a beginner should stay "
        "away. The downside is concrete; the upside is hopeful."
    ),
}


# All five definitions for the reference dictionary the UI shows
STANCE_DEFINITIONS: dict[str, dict[str, str]] = {
    "watch": {
        "pretty": "👀 Watch",
        "tagline": "No strong signal — keep an eye on it.",
        "trigger": "Sideways trend with neutral/weak news flow and no concrete red flags.",
    },
    "research_more": {
        "pretty": "🔍 Research more",
        "tagline": "Data is too thin to decide.",
        "trigger": "Few ticker-specific news items AND no clear price/momentum picture.",
    },
    "early_positive_setup": {
        "pretty": "🟢 Early positive setup",
        "tagline": "Chart + momentum aligned — but early, not confirmed.",
        "trigger": "Uptrend + price above 50-day average + MACD positive + RSI not stretched.",
    },
    "wait_for_confirmation": {
        "pretty": "🟡 Wait for confirmation",
        "tagline": "Signals are mixed — wait for the next catalyst.",
        "trigger": "Trend disagrees with momentum, OR price disagrees with news tone.",
    },
    "avoid_for_now": {
        "pretty": "🔴 Avoid for now",
        "tagline": "A specific negative is on the record.",
        "trigger": "Bearish regulatory/legal event, OR confirmed downtrend with bearish momentum.",
    },
}


# Jargon translations — same idea as the report renderer, but returned as
# structured data so the UI can show "(plain English: …)" inline.
_JARGON_HINTS: list[tuple[str, str]] = [
    ("50-day average",   "the average closing price over the last 50 days — a common 'is recent momentum positive' line"),
    ("SMA50",            "the 50-day average price"),
    ("MACD",             "MACD is a momentum gauge — positive = buyers stronger, negative = sellers stronger"),
    ("RSI",              "RSI is a 0–100 'how heavily bought / sold' score — below 30 = oversold, above 70 = overbought"),
    ("ATR",              "ATR = average daily price swing"),
    ("ticker-specific",  "specifically about this company (not general market news)"),
    ("regulatory",       "an action by the market regulator (SEBI/RBI) or government"),
    ("uptrend",          "a steady rise in price over recent weeks/months"),
    ("downtrend",        "a steady fall in price over recent weeks/months"),
    ("sentiment",        "the overall tone of recent news headlines (bullish, bearish, mixed, neutral)"),
]


def _gloss(reason: str) -> str | None:
    """Return a single plain-English gloss for the most relevant jargon term in `reason`."""
    rl = reason.lower()
    for key, plain in _JARGON_HINTS:
        if key.lower() in rl:
            return plain
    return None


# ---------------------------------------------------------------------------
# Public API

def build_stance_explanation(state: ResearchState) -> dict[str, Any]:
    label = state.stance.label
    reasons = state.stance.reasons or []
    rules_fired = [
        {"reason": r, "plain_english": _gloss(r)}
        for r in reasons
    ]
    return {
        "label": label,
        "label_pretty": STANCE_PRETTY.get(label, label),
        "score": state.stance.score,
        "confidence": state.confidence,
        "confidence_score": state.confidence_score,
        "headline": STANCE_HEADLINE.get(label, ""),
        "beginner_meaning": STANCE_BEGINNER_MEANING.get(label, ""),
        "rules_fired": rules_fired,
        "what_changes_view": list(state.stance.what_changes_view or []),
        "bull_points": list(state.stance.bull_points or []),
        "bear_points": list(state.stance.bear_points or []),
        # Reference dictionary — UI can show "what each of the 5 verdicts means"
        "stance_definitions": STANCE_DEFINITIONS,
    }
