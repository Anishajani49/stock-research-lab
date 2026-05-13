"""Deterministic stance engine — decides the leaning BEFORE the LLM is called.

The LLM is never allowed to pick the stance; it only explains what the rules
here produced. This is the main fix for "every ticker gets the same hedged
output": the leaning is now derived from concrete, per-ticker signals.

The 5 leanings (see schemas/output.py):
  - watch                    : no strong signal — just keep an eye on it
  - research_more            : data is too thin to decide
  - early_positive_setup     : bullish mix, but beginner should still confirm
  - wait_for_confirmation    : signals conflict; next earnings / event clarifies
  - avoid_for_now            : specific bad event (regulatory, fraud, crash)

Rules are applied in priority order. Each fired rule contributes a reason,
bull/bear points, and "what would change the view" items.
"""

from __future__ import annotations

import logging
from typing import Iterable

from app.schemas.output import (
    DevelopmentEvent,
    IndicatorSnapshot,
    RiskFlags,
    SentimentSummary,
    StanceDecision,
    StanceLabel,
    TrendLabel,
)

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helpers

def _fmt_ref(ev: DevelopmentEvent) -> str:
    refs = ", ".join(ev.evidence_ids) if ev.evidence_ids else ""
    return f" [ref: {refs}]" if refs else ""


def _as_bullet(ev: DevelopmentEvent) -> str:
    cat = ev.category
    src = f" — *{ev.source}*" if ev.source else ""
    return f"{ev.title}{src} ({cat}){_fmt_ref(ev)}"


def _has_critical_event(events: Iterable[DevelopmentEvent]) -> DevelopmentEvent | None:
    """Return the most severe bearish regulatory/legal event, if any."""
    worst: DevelopmentEvent | None = None
    for ev in events:
        if ev.category in {"regulatory", "legal"} and ev.polarity == "bearish" and ev.importance >= 4:
            if ev.ticker_match < 0.6:
                continue  # likely macro / not about this ticker
            if worst is None or ev.importance > worst.importance:
                worst = ev
    return worst


def _has_strong_positive_event(events: Iterable[DevelopmentEvent]) -> DevelopmentEvent | None:
    """Big bullish earnings / order win / rating upgrade that's ticker-specific."""
    best: DevelopmentEvent | None = None
    for ev in events:
        if ev.polarity != "bullish":
            continue
        if ev.category in {"earnings", "rating", "corporate", "product"} and ev.importance >= 3 and ev.ticker_match >= 0.6:
            if best is None or ev.importance > best.importance:
                best = ev
    return best


def _count_ticker_specific(events: Iterable[DevelopmentEvent], min_match: float = 0.6) -> int:
    return sum(1 for ev in events if ev.ticker_match >= min_match)


# -----------------------------------------------------------------------------
# Main engine

def decide_stance(
    events: list[DevelopmentEvent],
    indicators: IndicatorSnapshot,
    trend: TrendLabel,
    sentiment: SentimentSummary,
    risk: RiskFlags,
    missing: list[str] | None = None,
) -> StanceDecision:
    """Apply rules in priority order and return a fully-populated StanceDecision."""
    missing = missing or []
    reasons: list[str] = []
    bull_points: list[str] = []
    bear_points: list[str] = []
    change_view: list[str] = []
    used_ids: list[str] = []

    n_specific = _count_ticker_specific(events)
    critical = _has_critical_event(events)
    strong_pos = _has_strong_positive_event(events)

    # Build generic bull/bear bullet pools from the ranked events
    for ev in events:
        if ev.ticker_match < 0.4:
            continue
        if ev.polarity == "bullish":
            bull_points.append(_as_bullet(ev))
        elif ev.polarity == "bearish":
            bear_points.append(_as_bullet(ev))
        used_ids.extend(ev.evidence_ids)

    bull_points = bull_points[:6]
    bear_points = bear_points[:6]

    # ---- Derived indicator signals ----
    snap = indicators
    price_above_sma50 = (snap.last_close is not None and snap.sma50 is not None and snap.last_close > snap.sma50)
    price_below_sma50 = (snap.last_close is not None and snap.sma50 is not None and snap.last_close < snap.sma50)
    rsi_hot = snap.rsi14 is not None and snap.rsi14 > 70
    rsi_cold = snap.rsi14 is not None and snap.rsi14 < 30
    macd_bull = snap.macd_hist is not None and snap.macd_hist > 0
    macd_bear = snap.macd_hist is not None and snap.macd_hist < 0

    # -------------------------------------------------------------------------
    # RULE 1 — Critical bearish ticker-specific event → AVOID
    # -------------------------------------------------------------------------
    if critical is not None:
        reasons.append(
            f"Critical {critical.category} action against the company: "
            f"\"{critical.title}\"{_fmt_ref(critical)}."
        )
        if trend == "downtrend":
            reasons.append("Price trend is also downward — event pressure is confirmed on the chart.")
        change_view.extend([
            "A clear regulatory resolution, withdrawal of the order, or a settlement that removes the restriction.",
            "A subsequent quarter of in-line earnings showing the impact is contained.",
        ])
        score = -0.8 if trend == "downtrend" else -0.6
        return StanceDecision(
            label="avoid_for_now",
            score=score,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points or [_as_bullet(critical)],
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 2 — Very thin / missing data → RESEARCH MORE
    # We only fire this when BOTH news is thin AND indicators don't give
    # their own clear signal. A clean indicator picture (uptrend + macd_bull +
    # bullish sentiment, or equivalents) is itself a signal.
    # -------------------------------------------------------------------------
    has_indicator_signal = (
        (trend in {"uptrend", "downtrend"})
        and (macd_bull or macd_bear)
        and (snap.last_close is not None and snap.sma50 is not None)
    )
    data_is_thin = (
        (n_specific < 2 and not has_indicator_signal)
        or risk.weak_coverage
        or "market_data" in " ".join(missing).lower()
        or (sentiment.label == "insufficient" and not has_indicator_signal)
    )
    if data_is_thin:
        if n_specific < 2:
            reasons.append(f"Only {n_specific} ticker-specific item(s) were found in the fetched evidence.")
        if risk.weak_coverage:
            reasons.append("News coverage was flagged as weak by the risk checks.")
        if "market_data" in " ".join(missing).lower():
            reasons.append("Market data fetch failed — no chart to reason from.")
        change_view.extend([
            "Fresh, ticker-specific news from a major Indian outlet (ET / MC / Mint / BS).",
            "Successful market data fetch so trend + RSI + MACD can be computed.",
            "A full earnings report or investor transcript for this ticker.",
        ])
        return StanceDecision(
            label="research_more",
            score=0.0,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 3 — Downtrend + bearish momentum → AVOID FOR NOW
    # -------------------------------------------------------------------------
    if trend == "downtrend" and (sentiment.label in {"bearish", "mixed"} or macd_bear or risk.bearish_momentum):
        reasons.append("Price is in a downtrend.")
        if macd_bear:
            reasons.append("Momentum (MACD histogram) is negative — sellers still in control.")
        if sentiment.label == "bearish":
            reasons.append("News tone is bearish overall.")
        if risk.bearish_momentum:
            reasons.append("The risk checker flagged bearish momentum.")
        change_view.extend([
            "Price reclaiming its 50-day average with rising volume.",
            "MACD histogram turning and staying positive.",
            "A clearly positive catalyst (order win, earnings beat) covered by a named outlet.",
        ])
        return StanceDecision(
            label="avoid_for_now",
            score=-0.5,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 4 — Bullish setup → EARLY POSITIVE SETUP
    # Loosened: chart-only bullish alignment is enough. We do NOT require
    # sentiment.label=="bullish" (it almost never lands there on Indian
    # macro-heavy feeds), and we do NOT require a textbook positive event.
    # -------------------------------------------------------------------------
    bullish_chart = (
        trend == "uptrend"
        and price_above_sma50
        and macd_bull
        and not rsi_hot
    )
    if bullish_chart:
        reasons.append("Price is in an uptrend and trading above its 50-day average.")
        reasons.append("MACD momentum is positive — buying pressure is visible.")
        if sentiment.label == "bullish":
            reasons.append("News tone is bullish overall — sentiment confirms the chart.")
        elif sentiment.label in {"mixed", "neutral"}:
            reasons.append(
                f"News tone is {sentiment.label} — chart is leading; news is not yet confirming."
            )
        if strong_pos is not None:
            reasons.append(
                f"Specific positive event: \"{strong_pos.title}\"{_fmt_ref(strong_pos)}."
            )
        change_view.extend([
            "RSI spiking above 70 without news support (may indicate overheating).",
            "A sudden regulatory or legal negative affecting the company.",
            "Momentum rolling over (MACD turning negative) — would move this to wait_for_confirmation.",
        ])
        return StanceDecision(
            label="early_positive_setup",
            score=0.6 if (strong_pos is not None or sentiment.label == "bullish") else 0.4,
            reasons=reasons,
            bull_points=bull_points or ([_as_bullet(strong_pos)] if strong_pos else []),
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 4b — Recovery setup (price still below SMA50 but momentum turning
    # up). Was previously routed to "wait_for_confirmation" — now it's a real,
    # if cautious, positive lean.
    # -------------------------------------------------------------------------
    if price_below_sma50 and macd_bull and trend != "downtrend" and not rsi_hot:
        reasons.append(
            "Price is still below its 50-day average, but MACD momentum has turned positive — "
            "a possible early recovery, not yet confirmed by the trend."
        )
        if sentiment.label == "bullish":
            reasons.append("News tone is bullish — the recovery has some news support.")
        change_view.extend([
            "Price reclaiming the 50-day average on rising volume — would upgrade the setup.",
            "MACD rolling back below zero — would void the recovery thesis.",
            "A negative news catalyst (regulatory, weak earnings) — would void the recovery thesis.",
        ])
        return StanceDecision(
            label="early_positive_setup",
            score=0.3,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 5 — Overheated (uptrend + RSI > 70) → WAIT FOR CONFIRMATION
    # -------------------------------------------------------------------------
    if trend == "uptrend" and rsi_hot:
        reasons.append(f"Price is in an uptrend but RSI is {snap.rsi14:.0f} — historically heavy buying, stretched.")
        reasons.append("Upside is possible but a short-term cool-off is common after such readings.")
        change_view.extend([
            "RSI falling back towards 50 while the uptrend holds (healthier base).",
            "A positive earnings event that justifies the price level.",
        ])
        return StanceDecision(
            label="wait_for_confirmation",
            score=0.1,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 6 — Genuine conflict (chart says one thing, momentum opposite, or
    # the risk module flagged a contradiction). Tightened: we no longer fire
    # this just because sentiment is "mixed" during an uptrend — that's the
    # default state of Indian macro-heavy news feeds.
    # -------------------------------------------------------------------------
    real_conflict = (
        (price_above_sma50 and macd_bear)             # price up, momentum dying
        or (trend == "downtrend" and sentiment.label == "bullish")   # news vs chart
        or risk.conflicting_signals
    )
    if real_conflict:
        if price_above_sma50 and macd_bear:
            reasons.append("Price is above its 50-day average but momentum (MACD) is rolling over.")
        if trend == "downtrend" and sentiment.label == "bullish":
            reasons.append("News tone is bullish but the price is still in a downtrend — chart hasn't confirmed.")
        if risk.conflicting_signals:
            reasons.append("Risk checker flagged conflicting signals across price, momentum, and news.")
        change_view.extend([
            "Either MACD turning back up OR price closing back above the 50-day average.",
            "A clear earnings or regulatory catalyst that resolves the disagreement.",
        ])
        return StanceDecision(
            label="wait_for_confirmation",
            score=0.0,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 7 — Mild bearish lean → WATCH (with bear bias)
    # New: if the chart leans negative without a critical event, don't punt to
    # "wait" — call it "watch" with explicit bearish reasons.
    # -------------------------------------------------------------------------
    if (price_below_sma50 and (macd_bear or sentiment.label == "bearish")) or (
        trend == "downtrend" and sentiment.label in {"neutral", "mixed"}
    ):
        reasons.append("Chart is leaning negative without a single big bad event.")
        if price_below_sma50:
            reasons.append("Price is trading below its 50-day average — recent momentum is negative.")
        if macd_bear:
            reasons.append("MACD momentum is negative — sellers are still in control.")
        if sentiment.label == "bearish":
            reasons.append("News tone is bearish overall.")
        change_view.extend([
            "Price reclaiming the 50-day average on rising volume.",
            "A clearly positive catalyst (earnings beat, order win, rating upgrade).",
            "MACD turning and staying positive.",
        ])
        return StanceDecision(
            label="watch",
            score=-0.3,
            reasons=reasons,
            bull_points=bull_points,
            bear_points=bear_points,
            what_changes_view=change_view,
            used_evidence_ids=list(dict.fromkeys(used_ids)),
        )

    # -------------------------------------------------------------------------
    # RULE 8 — Sideways / quiet → WATCH
    # -------------------------------------------------------------------------
    reasons.append("No strong directional signals — trend is {0}, news tone is {1}.".format(
        trend, sentiment.label,
    ))
    if rsi_cold:
        reasons.append(f"RSI is {snap.rsi14:.0f} (heavily sold) — some bounce potential if news improves.")
    change_view.extend([
        "A catalyst (earnings, product launch, regulatory clarity) that tilts the story.",
        "A clean break above the 50-day average on rising volume.",
        "A decisive break below recent lows with bearish news.",
    ])
    return StanceDecision(
        label="watch",
        score=0.0,
        reasons=reasons,
        bull_points=bull_points,
        bear_points=bear_points,
        what_changes_view=change_view,
        used_evidence_ids=list(dict.fromkeys(used_ids)),
    )


# -----------------------------------------------------------------------------
# Pretty label for UI

STANCE_PRETTY: dict[StanceLabel, str] = {
    "watch":                 "👀 Watch",
    "research_more":         "🔍 Research more",
    "early_positive_setup":  "🟢 Early positive setup",
    "wait_for_confirmation": "🟡 Wait for confirmation",
    "avoid_for_now":         "🔴 Avoid for now",
}
