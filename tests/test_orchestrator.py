"""Tests for the orchestrator — adapters mocked."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.input import ResearchRequest


def _fake_market(ticker, timeframe="6mo", exchange="auto"):  # noqa: ARG001
    import numpy as np
    closes = np.linspace(100.0, 150.0, 260)
    ohlcv = []
    for i, c in enumerate(closes):
        ohlcv.append({
            "Date": f"2024-01-{i+1:03d}",
            "Open": float(c) * 0.99,
            "High": float(c) * 1.01,
            "Low":  float(c) * 0.98,
            "Close": float(c),
            "Volume": 1_000_000,
        })
    return {
        "ok": True, "error": None, "ticker": ticker, "timeframe": timeframe,
        "ohlcv": ohlcv,
        "meta": {
            "long_name": "Fake Corp", "sector": "Technology",
            "industry": "Software", "market_cap": 1e12,
            "pe": 30.0, "currency": "INR", "exchange": "NSE",
            "yf_symbol": f"{ticker}.NS",
        },
        "summary": {
            "last_close": 150.0, "period_return_pct": 50.0,
            "period_high": 150.0, "period_low": 100.0,
            "n_bars": 260, "start_date": "2024-01-001", "end_date": "2024-01-260",
        },
    }


def _fake_news(ticker, max_items=None, long_name=None):  # noqa: ARG001
    return {
        "ok": True, "error": None,
        "items": [
            {"title": f"{ticker} beats Q4 earnings, shares surge",
             "url": f"https://example.com/{ticker}/1", "source": "Economic Times",
             "published": "Mon, 01 Apr 2024 10:00:00 GMT",
             "snippet": "Strong earnings beat expectations with rising profit margins."},
            {"title": f"Analysts upgrade {ticker} on robust outlook",
             "url": f"https://example.com/{ticker}/2", "source": "MoneyControl",
             "published": "Mon, 01 Apr 2024 11:00:00 GMT",
             "snippet": "Upgrade cites growth momentum and new orders."},
            {"title": f"{ticker} wins new export order",
             "url": f"https://example.com/{ticker}/3", "source": "Business Standard",
             "published": "Mon, 01 Apr 2024 12:00:00 GMT",
             "snippet": "Company bags contract for next year."},
        ],
        "per_source_counts": {"Economic Times": 1, "MoneyControl": 1, "Business Standard": 1},
    }


def _fake_articles(urls, limit=None):  # noqa: ARG001
    return [{
        "ok": True, "error": None, "url": u,
        "title": "Strong growth reported", "text": "Robust results beat estimates.",
        "author": "", "date": "",
    } for u in urls]


def _fake_synthesize(state, client=None):  # noqa: ARG001
    from app.schemas.output import LLMExplanation
    eid = state.headlines[0]["evidence_id"] if state.headlines else ""
    return LLMExplanation(
        company_overview="Fake Corp makes software for Indian enterprises.",
        chart_plain_english="Price has trended higher over the period.",
        recent_changes="Earnings beat and new order win reported.",
        sources_say="ET and MoneyControl cover positive developments.",
        bull_case_text="Growth visibility improving.",
        bear_case_text="No specific bearish events in the evidence.",
        risks_text="Elevated volatility possible.",
        stance_explanation="Rules engine flagged an early positive setup.",
        cited_evidence=[eid] if eid else [],
    )


def test_orchestrator_end_to_end_with_mocks():
    req = ResearchRequest(ticker="FAKE", timeframe="6mo")

    with patch("app.orchestrator.market_yfinance.fetch_market", side_effect=_fake_market), \
         patch("app.orchestrator.news_rss.fetch_news", side_effect=_fake_news), \
         patch("app.orchestrator.blog_extractor.extract_many", side_effect=_fake_articles), \
         patch("app.orchestrator.synthesize", side_effect=_fake_synthesize):
        from app.orchestrator import run
        state = run(req)

    assert state.ticker == "FAKE"
    assert state.company_meta.get("long_name") == "Fake Corp"
    assert state.indicators.last_close == 150.0
    assert state.trend in {"uptrend", "unclear", "sideways", "downtrend"}
    assert len(state.headlines) == 3
    assert all(h.get("evidence_id") for h in state.headlines)
    assert state.sentiment.label in {"bullish", "mixed", "neutral"}
    assert state.confidence in {"Low", "Medium", "High"}
    assert state.llm is not None
    # LLM citations must reference only known evidence
    known_ids = set(state.evidence_ids)
    for cid in state.llm.cited_evidence:
        assert cid in known_ids
    # Deterministic stance should be set
    assert state.stance.label in {
        "watch", "research_more", "early_positive_setup",
        "wait_for_confirmation", "avoid_for_now",
    }
    # Developments should have been extracted from news
    assert len(state.developments) > 0


def test_orchestrator_handles_market_failure():
    req = ResearchRequest(ticker="BAD", timeframe="6mo")

    def _bad_market(ticker, timeframe="6mo", exchange="auto"):  # noqa: ARG001
        return {"ok": False, "error": "invalid ticker", "ohlcv": [], "meta": {}, "summary": {}}

    def _empty_news(ticker, max_items=None, long_name=None):  # noqa: ARG001
        return {"ok": True, "error": None, "items": [], "per_source_counts": {}}

    with patch("app.orchestrator.market_yfinance.fetch_market", side_effect=_bad_market), \
         patch("app.orchestrator.news_rss.fetch_news", side_effect=_empty_news), \
         patch("app.orchestrator.synthesize", side_effect=_fake_synthesize):
        from app.orchestrator import run
        state = run(req)

    assert any("market_data" in m for m in state.missing)
    assert state.confidence == "Low"
    # Should still produce a fallback explanation
    assert state.llm is not None
    # With no market and no news, the stance engine should pick research_more
    assert state.stance.label == "research_more"
