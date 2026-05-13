"""Tests for the lexicon-based sentiment engine."""

from __future__ import annotations

from app.analysis.sentiment import compute_sentiment, _score_text


def test_score_text_positive():
    s, p, n = _score_text("Shares surge on strong earnings beat")
    assert p > 0
    assert n == 0
    assert s > 0.5


def test_score_text_negative():
    s, p, n = _score_text("Company warns of weak guidance; stock plunges after downgrade")
    assert n > 0
    assert p == 0
    assert s < -0.5


def test_score_text_negation_flips():
    # "not strong" should NOT count as positive
    s1, p1, _ = _score_text("the report is not strong")
    s2, _, n2 = _score_text("the report is strong")
    assert p1 == 0
    assert s1 <= 0
    assert s2 > 0
    assert n2 == 0


def test_compute_sentiment_insufficient():
    summary = compute_sentiment(headlines=[], articles=[], transcripts=[])
    assert summary.label == "insufficient"
    assert summary.score == 0.0


def test_compute_sentiment_bullish():
    headlines = [
        {"title": "Revenue beats estimates, stock surges", "snippet": ""},
        {"title": "Analyst upgrades to buy on strong outlook", "snippet": ""},
        {"title": "Record quarter boosts confidence", "snippet": ""},
    ]
    summary = compute_sentiment(headlines, [], [])
    assert summary.label == "bullish"
    assert summary.score > 0.25


def test_compute_sentiment_bearish():
    headlines = [
        {"title": "Company warns of weakness; stock slumps", "snippet": ""},
        {"title": "Analyst downgrade cites elevated risk", "snippet": ""},
        {"title": "Lawsuit probe weighs on shares", "snippet": ""},
    ]
    summary = compute_sentiment(headlines, [], [])
    assert summary.label == "bearish"
    assert summary.score < -0.25


def test_compute_sentiment_article_weighted_more():
    headlines = [{"title": "Stock falls on warning", "snippet": ""}]
    articles = [
        {"ok": True, "title": "",
         "text": "Strong growth, record revenue, analyst upgrade, bullish outlook, robust gains"},
    ]
    summary = compute_sentiment(headlines, articles, [])
    # Article sentiment weight x2 should dominate
    assert summary.score > 0
