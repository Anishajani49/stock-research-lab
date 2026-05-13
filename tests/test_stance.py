"""Tests for the deterministic stance engine."""

from __future__ import annotations

from app.analysis.stance import decide_stance
from app.schemas.output import (
    DevelopmentEvent,
    IndicatorSnapshot,
    RiskFlags,
    SentimentSummary,
)


def _evt(**kw) -> DevelopmentEvent:
    defaults = dict(
        evidence_ids=["e1"], category="other", polarity="neutral",
        importance=1, title="An event", snippet="", source="ET",
        published="", ticker_match=0.9, age_days=1.0,
    )
    defaults.update(kw)
    return DevelopmentEvent(**defaults)


def test_regulatory_event_triggers_avoid_for_now():
    events = [_evt(category="regulatory", polarity="bearish", importance=5,
                    title="SEBI bans promoter from trading")]
    stance = decide_stance(
        events, IndicatorSnapshot(last_close=100, sma50=110),
        trend="downtrend",
        sentiment=SentimentSummary(label="bearish", score=-0.4),
        risk=RiskFlags(),
    )
    assert stance.label == "avoid_for_now"
    assert any("regulatory" in r.lower() or "sebi" in r.lower() for r in stance.reasons)


def test_thin_data_triggers_research_more():
    stance = decide_stance(
        [], IndicatorSnapshot(), trend="unclear",
        sentiment=SentimentSummary(label="insufficient"),
        risk=RiskFlags(weak_coverage=True),
        missing=["market_data (no data)"],
    )
    assert stance.label == "research_more"


def test_clean_bullish_setup_triggers_early_positive():
    events = [_evt(category="earnings", polarity="bullish", importance=4,
                    title="Company beats Q3 earnings")]
    stance = decide_stance(
        events,
        IndicatorSnapshot(last_close=150, sma50=140, rsi14=55, macd_hist=1.2),
        trend="uptrend",
        sentiment=SentimentSummary(label="bullish", score=0.3, n_headlines=10),
        risk=RiskFlags(),
    )
    assert stance.label == "early_positive_setup"
    assert any(b for b in stance.bull_points)


def test_overheated_uptrend_triggers_wait_for_confirmation():
    stance = decide_stance(
        [_evt(category="earnings", polarity="bullish", importance=3,
              title="Strong quarter reported")],
        IndicatorSnapshot(last_close=200, sma50=180, rsi14=82, macd_hist=2.0),
        trend="uptrend",
        sentiment=SentimentSummary(label="bullish", score=0.2, n_headlines=10),
        risk=RiskFlags(),
    )
    assert stance.label == "wait_for_confirmation"


def test_conflicting_signals_trigger_wait():
    stance = decide_stance(
        [_evt(category="earnings", polarity="bearish", importance=3,
              title="Q3 results miss estimates"),
         _evt(category="earnings", polarity="bearish", importance=3,
              title="Margins contract further"),
         _evt(category="product", polarity="bullish", importance=2,
              title="New plant launched")],
        IndicatorSnapshot(last_close=120, sma50=100, rsi14=60, macd_hist=-0.5),
        trend="uptrend",
        sentiment=SentimentSummary(label="mixed", score=-0.05, n_headlines=10),
        risk=RiskFlags(conflicting_signals=True),
    )
    assert stance.label == "wait_for_confirmation"


def test_sideways_with_no_signals_triggers_watch():
    stance = decide_stance(
        [_evt(category="earnings", polarity="neutral", importance=2,
              title="Company hosts analyst meet"),
         _evt(category="earnings", polarity="neutral", importance=2,
              title="Regular corporate update"),
         _evt(category="earnings", polarity="neutral", importance=2,
              title="Annual report filed")],
        IndicatorSnapshot(last_close=100, sma50=100, rsi14=50, macd_hist=0.0),
        trend="sideways",
        sentiment=SentimentSummary(label="neutral", n_headlines=8),
        risk=RiskFlags(),
    )
    assert stance.label == "watch"
