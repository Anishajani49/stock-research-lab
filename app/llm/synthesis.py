"""Synthesis — build the LLM context around the deterministic stance.

The stance engine has already decided the leaning before we get here. We hand
the LLM the stance, the ranked developments, and a compact evidence list, and
ask it to produce an LLMExplanation (text only, no decisions).
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.guardrails import apply_guardrails, coerce_explanation
from app.llm.ollama_client import OllamaClient, OllamaError
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas.output import LLMExplanation, ResearchState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context builders

def _compact_indicators(state: ResearchState) -> dict[str, Any]:
    snap = state.indicators
    return {
        "trend_label": state.trend,
        "last_close": snap.last_close,
        "price_vs_sma50": (
            "above" if (snap.last_close and snap.sma50 and snap.last_close > snap.sma50)
            else "below" if (snap.last_close and snap.sma50)
            else "n/a"
        ),
        "rsi14": snap.rsi14,
        "rsi_label": (
            "oversold" if snap.rsi14 is not None and snap.rsi14 < 30 else
            "overbought" if snap.rsi14 is not None and snap.rsi14 > 70 else
            "neutral" if snap.rsi14 is not None else "n/a"
        ),
        "macd_hist": snap.macd_hist,
        "macd_label": (
            "bullish" if snap.macd_hist is not None and snap.macd_hist > 0 else
            "bearish" if snap.macd_hist is not None and snap.macd_hist < 0 else "n/a"
        ),
        "volume_trend": snap.volume_trend,
    }


def _shrink_evidence(
    state: ResearchState,
    max_headlines: int = 20,
    max_articles: int = 6,
    max_transcripts: int = 3,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for h in state.headlines[:max_headlines]:
        if not h.get("evidence_id"):
            continue
        items.append({
            "evidence_id": h["evidence_id"],
            "kind": "headline",
            "source": h.get("source") or "",
            "published": h.get("published") or "",
            "title": (h.get("title") or "")[:220],
            "snippet": (h.get("snippet") or "")[:350],
        })
    for a in state.articles[:max_articles]:
        if not a.get("ok") or not a.get("evidence_id"):
            continue
        items.append({
            "evidence_id": a["evidence_id"],
            "kind": "article",
            "source": a.get("source_domain") or "",
            "published": a.get("date") or "",
            "title": (a.get("title") or a.get("url") or "")[:220],
            "url": a.get("final_url") or a.get("url"),
            "snippet": (a.get("text") or "")[:2200],
        })
    for t in state.transcripts[:max_transcripts]:
        if not t.get("ok") or not t.get("evidence_id"):
            continue
        items.append({
            "evidence_id": t["evidence_id"],
            "kind": "youtube",
            "url": t.get("url"),
            "snippet": (t.get("text") or "")[:1800],
        })
    return items


def _compact_developments(state: ResearchState, limit: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in state.developments[:limit]:
        out.append({
            "evidence_ids": ev.evidence_ids,
            "category": ev.category,
            "polarity": ev.polarity,
            "importance": ev.importance,
            "ticker_match": round(ev.ticker_match, 2),
            "age_days": ev.age_days,
            "title": ev.title,
            "snippet": ev.snippet,
            "source": ev.source,
        })
    return out


def build_context(state: ResearchState) -> dict[str, Any]:
    is_mf = (state.company_meta or {}).get("instrument_type") == "mutual_fund"
    return {
        "ticker": state.ticker,
        "instrument_type": "mutual_fund" if is_mf else "equity",
        "timeframe": state.timeframe,
        "company_meta": {
            k: v for k, v in (state.company_meta or {}).items()
            if k in {"long_name", "sector", "industry", "exchange", "currency",
                     "market_cap", "pe", "fund_house", "scheme_category", "scheme_type"}
        },
        "price_summary": state.price_series_summary,
        "technicals": _compact_indicators(state),
        "sentiment": state.sentiment.model_dump(),
        "risk_flags": state.risk.model_dump(),
        "confidence_level": state.confidence,
        "confidence_score": state.confidence_score,
        "missing_data": state.missing,
        # The decision — FIXED, not up for the LLM to change
        "deterministic_stance": state.stance.model_dump(),
        "developments": _compact_developments(state),
        "evidence": _shrink_evidence(state),
    }


# ---------------------------------------------------------------------------
# Entry point

def synthesize(state: ResearchState, client: OllamaClient | None = None) -> LLMExplanation:
    client = client or OllamaClient()
    ctx = build_context(state)
    prompt = build_user_prompt(ctx)
    allowed_ids = {e["evidence_id"] for e in ctx["evidence"] if e.get("evidence_id")}

    try:
        raw = client.generate_json(prompt, system=SYSTEM_PROMPT, temperature=0.4)
    except OllamaError as e:
        log.error("Ollama synthesis failed: %s", e)
        return _fallback_explanation(state, reason=str(e))

    if not isinstance(raw, dict):
        return _fallback_explanation(state, reason="LLM returned non-object JSON")

    explanation = coerce_explanation(raw)
    explanation = apply_guardrails(explanation, allowed_evidence_ids=allowed_ids)
    return explanation


# ---------------------------------------------------------------------------
# Deterministic fallback — used when Ollama is unavailable

def _fmt_ev_ids(ids: list[str]) -> str:
    return f" [ref: {', '.join(ids)}]" if ids else ""


def _fallback_explanation(state: ResearchState, reason: str) -> LLMExplanation:
    meta = state.company_meta or {}
    name = meta.get("long_name") or state.ticker
    sector = meta.get("sector") or "(sector not specified)"
    industry = meta.get("industry") or "(industry not specified)"

    # Use top developments (already ranked) for narrative
    top = state.developments[:6]
    top_bull = [ev for ev in top if ev.polarity == "bullish"]
    top_bear = [ev for ev in top if ev.polarity == "bearish"]
    top_neut = [ev for ev in top if ev.polarity == "neutral"]

    def _to_line(ev) -> str:
        return f"• {ev.title} — *{ev.source or ev.category}*{_fmt_ev_ids(ev.evidence_ids)}"

    snap = state.indicators
    last = snap.last_close
    pct = (state.price_series_summary or {}).get("period_return_pct")

    # Plain-English summary instead of dumping headlines (which the report
    # already shows above this section).
    if top:
        n_bull = sum(1 for ev in top if ev.polarity == "bullish")
        n_bear = sum(1 for ev in top if ev.polarity == "bearish")
        n_neut = len(top) - n_bull - n_bear
        cats = sorted({ev.category for ev in top})
        mood = (
            "skews negative" if n_bear > n_bull else
            "skews positive" if n_bull > n_bear else
            "is mixed"
        )
        recent_lines = (
            f"Across the {len(top)} most-relevant items, news flow {mood} "
            f"({n_bull} positive, {n_bear} negative, {n_neut} neutral). "
            f"Categories present: {', '.join(cats)}. "
            f"_(Auto-summary — the LLM was unavailable; see the bullet list above for the raw items.)_"
        )
    else:
        recent_lines = (
            "No ticker-specific events surfaced — only generic market coverage. "
            "Try again later or check a longer timeframe."
        )

    sources_line = "News coverage includes: " + \
        ", ".join(sorted({h.get("source") or "" for h in state.headlines if h.get("source")})) \
        if state.headlines else "No named outlets were captured in the evidence."

    bull_txt = "\n".join(_to_line(ev) for ev in top_bull) or \
        "No clearly bullish events were found in the fetched evidence."
    bear_txt = "\n".join(_to_line(ev) for ev in top_bear) or \
        "No clearly bearish events were found in the fetched evidence."

    risk_bits: list[str] = []
    if state.risk.regulatory_event:
        risk_bits.append("A regulatory action is visible in the evidence.")
    if state.risk.bearish_momentum:
        risk_bits.append("Momentum is bearish — price and MACD agree on selling pressure.")
    if state.risk.weak_coverage:
        risk_bits.append("News coverage is thin, which lowers confidence in any read.")
    if state.risk.conflicting_signals:
        risk_bits.append("Price and news are pointing in different directions.")
    if not risk_bits:
        risk_bits.append("No automated risk flags fired on this run.")

    return LLMExplanation(
        company_overview=(
            f"{name} is listed on {meta.get('exchange') or 'an Indian exchange'}. "
            f"Sector: {sector}. Industry: {industry}. "
            f"(Automated fallback — LLM unavailable: {reason})"
        ),
        chart_plain_english=(
            f"Over the period {state.timeframe} the price moved by about "
            f"{pct if pct is not None else 'n/a'}%, with last close "
            f"{last if last is not None else 'n/a'}. The trend label is {state.trend}."
        ),
        recent_changes=recent_lines,
        sources_say=sources_line,
        bull_case_text=bull_txt,
        bear_case_text=bear_txt,
        risks_text="\n".join(f"- {r}" for r in risk_bits),
        stance_explanation=(
            "Stance **" + state.stance.label + "** was chosen by the rules engine because:\n"
            + "\n".join(f"- {r}" for r in state.stance.reasons[:5])
            if state.stance.reasons else
            "Stance was chosen by the rules engine; no reasons were produced."
        ),
        cited_evidence=state.stance.used_evidence_ids[:20],
    )
