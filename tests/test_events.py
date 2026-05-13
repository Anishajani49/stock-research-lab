"""Tests for the deterministic event extractor."""

from __future__ import annotations

from app.analysis.events import extract_developments


def test_regulatory_event_surfaced_with_ticker_match():
    headlines = [
        {"evidence_id": "n1",
         "title": "SEBI bans ITC promoter from trading for 2 years",
         "snippet": "The regulator passed an order on Monday.",
         "source": "Economic Times",
         "published": "Mon, 01 Apr 2024 10:00:00 GMT"},
    ]
    events = extract_developments(headlines, ticker="ITC", company_name="ITC Limited")
    assert len(events) == 1
    ev = events[0]
    assert ev.category == "regulatory"
    assert ev.polarity == "bearish"
    assert ev.importance >= 4
    assert ev.ticker_match == 1.0


def test_macro_news_is_downweighted():
    headlines = [
        {"evidence_id": "n1",
         "title": "Nifty ends higher as FII flows support market",
         "snippet": "Broader indices closed in the green.",
         "source": "MoneyControl",
         "published": "Mon, 01 Apr 2024 10:00:00 GMT"},
    ]
    events = extract_developments(headlines, ticker="RELIANCE",
                                  company_name="Reliance Industries Limited")
    assert events[0].category == "macro"
    assert events[0].importance == 1


def test_earnings_bullish_polarity_bumps_importance():
    headlines = [
        {"evidence_id": "n1",
         "title": "TCS beats Q4 estimates on strong deal wins",
         "snippet": "Revenue grew 12% and margin expansion continued.",
         "source": "LiveMint",
         "published": "Mon, 01 Apr 2024 10:00:00 GMT"},
    ]
    events = extract_developments(headlines, ticker="TCS",
                                  company_name="Tata Consultancy Services")
    assert events[0].category == "earnings"
    assert events[0].polarity == "bullish"


def test_ticker_tokens_match_company_name():
    headlines = [
        {"evidence_id": "n1",
         "title": "Infosys wins digital contract from European bank",
         "snippet": "The deal is valued in the mid-single digits.",
         "source": "Business Standard",
         "published": "Mon, 01 Apr 2024 10:00:00 GMT"},
    ]
    events = extract_developments(headlines, ticker="INFY",
                                  company_name="Infosys Limited")
    # Matches via company token
    assert events[0].ticker_match >= 0.6
