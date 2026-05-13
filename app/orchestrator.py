"""Orchestrator — runs adapters in parallel, then event → ranking → stance → LLM.

Two entry points:
  - run(request)       → full stock analysis pipeline
  - run_learn(request) → candlestick learning mode (can optionally pull OHLCV
                         to show real detections, but never calls the LLM)
"""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from app.adapters import (
    blog_extractor,
    chart_image,
    fundamentals as fundamentals_adapter,
    market_yfinance,
    mfapi,
    news_rss,
    youtube_transcript,
)
from app.analysis.confidence import score_confidence
from app.analysis.events import extract_developments
from app.analysis.indicators import compute_indicators
from app.analysis.ranking import rank_events
from app.analysis.risk_rules import evaluate_risks
from app.analysis.sentiment import compute_sentiment
from app.analysis.stance import decide_stance
from app.analysis.trend import classify_trend
from app.learn import build_lesson
from app.llm.synthesis import synthesize
from app.schemas.evidence import Evidence
from app.schemas.input import ResearchRequest
from app.schemas.output import LearningLesson, ResearchState
from app.storage.db import init_db, insert_evidence

log = logging.getLogger(__name__)


def _evidence_id(source_type: str, key: str) -> str:
    h = hashlib.sha1(f"{source_type}|{key}".encode("utf-8")).hexdigest()[:12]
    return f"{source_type[:3]}_{h}"


def _select_article_urls(headlines: list[dict[str, Any]], limit: int) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for h in headlines:
        u = (h.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        urls.append(u)
        if len(urls) >= limit:
            break
    return urls


def _run_market_step(request: ResearchRequest) -> dict[str, Any]:
    if request.is_mutual_fund:
        code = request.mf_scheme_code
        if not code:
            code, _ = mfapi.resolve_scheme(request.ticker)
            if not code:
                return {
                    "ok": False,
                    "error": f"Could not resolve mutual fund from '{request.ticker}'",
                    "ohlcv": [], "meta": {}, "summary": {},
                }
        return mfapi.fetch_nav_history(code, request.timeframe)
    return market_yfinance.fetch_market(request.ticker, request.timeframe, request.exchange)


# =============================================================================
# LEARNING MODE
# =============================================================================

def run_learn(request: ResearchRequest) -> LearningLesson:
    """Build a deterministic candlestick lesson.
    If a ticker is supplied AND market data is available, real pattern
    detections are attached. No LLM calls.
    """
    ohlcv: list[dict[str, Any]] = []
    company_name: str | None = None

    if request.ticker:
        try:
            market = _run_market_step(request)
            if market.get("ok"):
                ohlcv = market.get("ohlcv") or []
                company_name = (market.get("meta") or {}).get("long_name")
        except Exception as e:
            log.warning("learn-mode market fetch failed: %s", e)

    lesson = build_lesson(
        ticker=request.ticker or None,
        ohlcv=ohlcv,
        company_name=company_name,
        timeframe=request.timeframe,
    )
    return lesson


# =============================================================================
# ANALYSIS MODE
# =============================================================================

def run(request: ResearchRequest) -> ResearchState:
    """Full pipeline: adapters → deterministic analytics → stance → LLM explain."""
    init_db()

    state = ResearchState(ticker=request.ticker, timeframe=request.timeframe)
    missing: list[str] = []
    evidence_items: list[Evidence] = []

    # --- 1. Market / NAV ---
    market = _run_market_step(request)

    if market.get("ok"):
        state.company_meta = market.get("meta", {}) or {}
        state.price_series_summary = market.get("summary", {}) or {}
        ohlcv = market.get("ohlcv", []) or []
        state.ohlcv = ohlcv
        state.indicators = compute_indicators(ohlcv)
        state.trend = classify_trend(state.indicators)
        resolved_ticker = market.get("ticker") or request.ticker
        meta_eid = _evidence_id(
            "market_data" if not request.is_mutual_fund else "meta",
            f"{resolved_ticker}|{request.timeframe}",
        )
        evidence_items.append(Evidence(
            evidence_id=meta_eid,
            source_type="market_data" if not request.is_mutual_fund else "meta",
            title=(
                f"{'NAV' if request.is_mutual_fund else 'Market'} data: "
                f"{state.company_meta.get('long_name') or resolved_ticker} "
                f"({request.timeframe})"
            ),
            url=None,
            snippet=(
                f"bars={state.price_series_summary.get('n_bars')}, "
                f"last={state.price_series_summary.get('last_close')}, "
                f"ret%={state.price_series_summary.get('period_return_pct')}"
            ),
            quality_score=0.9,
        ))
    else:
        label = "mutual_fund_nav" if request.is_mutual_fund else "market_data"
        missing.append(f"{label} ({market.get('error', 'unknown error')})")

    long_name = state.company_meta.get("long_name") if market.get("ok") else None
    news_query_ticker = request.ticker if not request.is_mutual_fund else (long_name or request.ticker)

    # --- 1b. Fundamentals + upcoming events (equity only — these come from
    # the same upstream sources Zerodha/Groww use; cached for 6h) ---
    if not request.is_mutual_fund and market.get("ok"):
        yf_symbol = state.company_meta.get("yf_symbol") or market.get("ticker")
        try:
            fund_pkg = fundamentals_adapter.fetch_fundamentals(yf_symbol)
            if fund_pkg.get("ok"):
                state.fundamentals = fund_pkg.get("fundamentals") or {}
                state.upcoming_events = fund_pkg.get("upcoming_events") or []
            else:
                missing.append(f"fundamentals ({fund_pkg.get('error')})")
        except Exception as e:
            log.warning("fundamentals fetch failed for %s: %s", yf_symbol, e)
            missing.append(f"fundamentals ({e})")

    # --- 2. Parallel: news + chart + youtube ---
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures: dict[str, Any] = {
            "news": pool.submit(news_rss.fetch_news, news_query_ticker, None, long_name),
        }
        if request.chart_image:
            futures["chart"] = pool.submit(chart_image.parse_chart, request.chart_image)
        if request.youtube_urls:
            futures["yt"] = pool.submit(youtube_transcript.fetch_many, request.youtube_urls)

        results: dict[str, Any] = {}
        for name, fut in list(futures.items()):
            try:
                results[name] = fut.result()
            except Exception as e:
                log.exception("Adapter %s failed", name)
                results[name] = {"ok": False, "error": str(e)}

    # --- Headlines ---
    news = results.get("news", {})
    headlines = news.get("items", []) if news.get("ok") else []
    for h in headlines:
        eid = _evidence_id("news_rss", h.get("url") or h.get("title", ""))
        h["evidence_id"] = eid
        evidence_items.append(Evidence(
            evidence_id=eid, source_type="news_rss",
            title=h.get("title", "")[:240], url=h.get("url"),
            snippet=(h.get("snippet") or "")[:500], quality_score=0.6,
        ))
    state.headlines = headlines
    if not headlines:
        missing.append("news_headlines")

    # --- Articles ---
    urls = _select_article_urls(headlines, limit=6)
    articles = blog_extractor.extract_many(urls) if urls else []
    for a in articles:
        if not a.get("ok"):
            continue
        eid = _evidence_id("article", a.get("url", ""))
        a["evidence_id"] = eid
        evidence_items.append(Evidence(
            evidence_id=eid, source_type="article",
            title=(a.get("title") or a.get("url") or "")[:240],
            url=a.get("url"), snippet=(a.get("text") or "")[:500],
            quality_score=0.75,
        ))
    state.articles = articles

    # --- YouTube ---
    transcripts = results.get("yt") or []
    for t in transcripts:
        if not t.get("ok"):
            continue
        eid = _evidence_id("youtube", t.get("video_id") or t.get("url", ""))
        t["evidence_id"] = eid
        evidence_items.append(Evidence(
            evidence_id=eid, source_type="youtube",
            title=f"YouTube transcript {t.get('video_id','')}",
            url=t.get("url"), snippet=(t.get("text") or "")[:500],
            quality_score=0.55,
        ))
    state.transcripts = transcripts
    if request.youtube_urls and not any(t.get("ok") for t in transcripts):
        missing.append("youtube_transcripts")

    # --- Chart ---
    chart = results.get("chart")
    if chart:
        if chart.get("ok"):
            eid = _evidence_id("chart_image", str(request.chart_image))
            chart["evidence_id"] = eid
            evidence_items.append(Evidence(
                evidence_id=eid, source_type="chart_image",
                title=f"Chart OCR: {request.chart_image}", url=None,
                snippet=(chart.get("summary") or "")[:500], quality_score=0.4,
            ))
            state.chart_notes = chart
        else:
            missing.append(f"chart_image ({chart.get('error')})")

    # --- 3. Deterministic analytics ---
    state.sentiment = compute_sentiment(state.headlines, state.articles, state.transcripts)
    state.risk = evaluate_risks(
        state.indicators, state.trend, state.sentiment,
        state.headlines, state.price_series_summary,
    )

    flags = {
        "market": bool(market.get("ok")),
        "indicators": state.indicators.last_close is not None,
        "news": bool(headlines),
        "articles": any(a.get("ok") for a in state.articles),
    }
    state.confidence, state.confidence_score = score_confidence(
        state.indicators, state.trend, state.sentiment, state.headlines, flags,
    )

    # --- 4. Event extraction + ranking ---
    raw_events = extract_developments(
        state.headlines, state.articles,
        ticker=request.ticker, company_name=long_name,
    )
    ranked_events = rank_events(raw_events, top_k=12)

    # Promote regulatory flag on risk based on extracted events
    if any(ev.category == "regulatory" and ev.polarity == "bearish"
           and ev.ticker_match >= 0.6 for ev in ranked_events):
        state.risk.regulatory_event = True
        if "Regulatory action detected in evidence." not in state.risk.details:
            state.risk.details.append("Regulatory action detected in evidence.")

    state.developments = ranked_events

    # --- 5. Deterministic stance ---
    state.stance = decide_stance(
        ranked_events, state.indicators, state.trend,
        state.sentiment, state.risk, missing,
    )

    # Mention the nearest upcoming corporate event in "what would change view"
    # so the report tells the beginner what concrete date to watch for.
    near_term = [
        ev for ev in (state.upcoming_events or [])
        if ev.get("days_until") is not None and 0 <= ev["days_until"] <= 30
    ]
    if near_term:
        ev = near_term[0]
        kind_label = {
            "earnings": "Quarterly earnings",
            "ex_dividend": "Ex-dividend date",
            "dividend_payment": "Dividend payment",
        }.get(ev.get("kind", ""), "Upcoming corporate event")
        state.stance.what_changes_view.insert(
            0,
            f"Upcoming **{kind_label}** on {ev.get('date')} (in {ev['days_until']} days) — "
            f"this can shift the view materially in either direction."
        )

    # --- Persist evidence ---
    try:
        insert_evidence(evidence_items)
    except Exception as e:
        log.warning("Failed to persist evidence: %s", e)
    state.evidence_ids = [e.evidence_id for e in evidence_items]
    state.missing = missing

    # --- 6. LLM explanation ---
    try:
        state.llm = synthesize(state)
    except Exception as e:
        log.exception("Synthesis failed: %s", e)
        from app.llm.synthesis import _fallback_explanation
        state.llm = _fallback_explanation(state, reason=str(e))

    state.company_meta.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    state.company_meta.setdefault(
        "instrument_type", "mutual_fund" if request.is_mutual_fund else "equity"
    )
    return state
