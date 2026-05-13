"""Tests for LLM guardrails (explainer-shape output)."""

from __future__ import annotations

from app.llm.guardrails import (
    apply_guardrails,
    coerce_explanation,
    contains_forbidden,
    filter_citations,
    sanitize_text,
)


def test_sanitize_rewrites_buy_now():
    out = sanitize_text("You should buy now before it's too late.")
    assert "buy now" not in out.lower()


def test_sanitize_rewrites_will_rise():
    out = sanitize_text("The stock will rise next quarter.")
    assert "will rise" not in out.lower()
    assert "may rise" in out.lower()


def test_sanitize_rewrites_guaranteed():
    out = sanitize_text("This is a guaranteed winner.")
    assert "guaranteed" not in out.lower()


def test_sanitize_removes_price_target():
    out = sanitize_text("Analysts set a price target of 250.")
    assert "price target" not in out.lower()


def test_contains_forbidden_detects_banned_phrases():
    hits = contains_forbidden("Buy now — guaranteed profit!")
    assert len(hits) >= 1


def test_filter_citations_drops_unknown():
    allowed = {"abc_1", "def_2"}
    got = filter_citations(["abc_1", "xxx", "def_2", ""], allowed)
    assert got == ["abc_1", "def_2"]


def test_coerce_explanation_normalizes_lists():
    raw = {
        "company_overview": "It makes stuff.",
        "cited_evidence": "abc_1, def_2",
    }
    r = coerce_explanation(raw)
    assert r.company_overview
    assert r.cited_evidence  # coerced from string


def test_apply_guardrails_end_to_end():
    raw = {
        "company_overview": "You should buy now! Guaranteed returns.",
        "chart_plain_english": "Price will rise soon.",
        "recent_changes": "Earnings beat.",
        "sources_say": "Very bullish.",
        "bull_case_text": "Growth is strong.",
        "bear_case_text": "Regulatory risk.",
        "risks_text": "Sell now if it falls.",
        "stance_explanation": "Leaning cautious.",
        "cited_evidence": ["known_id", "bogus_id"],
    }
    r = coerce_explanation(raw)
    r = apply_guardrails(r, allowed_evidence_ids={"known_id"})
    assert "buy now" not in r.company_overview.lower()
    assert "guaranteed" not in r.company_overview.lower()
    assert "will rise" not in r.chart_plain_english.lower()
    assert "sell now" not in r.risks_text.lower()
    assert r.cited_evidence == ["known_id"]
