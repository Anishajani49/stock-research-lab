"""8-step analyst-style walk-through — uses real numbers from the analysis run.

This is the "how professionals think" section. We do not give buy/sell advice —
we narrate the structured questions a professional would ask, and the
observations those questions produce when applied to this specific stock.
"""

from __future__ import annotations

from typing import Any

from app.schemas.output import ResearchState


def _to_pct(v: float | None) -> float | None:
    if v is None:
        return None
    f = float(v)
    if abs(f) <= 1.5:
        return f * 100.0
    return f


def _step1_business(state: ResearchState) -> dict[str, Any]:
    meta = state.company_meta or {}
    name = meta.get("long_name") or state.ticker
    sector = meta.get("sector") or "(sector data unavailable)"
    industry = meta.get("industry") or "(industry data unavailable)"
    obs = (
        f"**{name}** operates in the **{industry}** industry, classified under the "
        f"**{sector}** sector."
    )
    return {
        "step": 1,
        "title": "Understand the business",
        "questions": [
            "What does this company actually sell?",
            "Who are its customers?",
            "Is the industry growing or shrinking?",
            "Does the business have a moat (something that keeps competitors out)?",
        ],
        "observation": obs,
        "beginner_tip": (
            "If you cannot explain to a friend in two sentences what this company does "
            "and how it makes money, you are not ready to study it as an investment."
        ),
    }


def _step2_growth(state: ResearchState) -> dict[str, Any]:
    f = state.fundamentals or {}
    rg = _to_pct(f.get("revenue_growth"))
    eg = _to_pct(f.get("earnings_growth"))
    bits: list[str] = []
    if rg is not None:
        bits.append(f"Revenue is changing {rg:+.1f}% year-over-year.")
    if eg is not None:
        bits.append(f"Earnings are changing {eg:+.1f}% year-over-year.")
    obs = " ".join(bits) if bits else "Growth numbers were not available from the data feed."
    return {
        "step": 2,
        "title": "Check growth",
        "questions": [
            "Is revenue growing year-over-year?",
            "Is profit growing faster, slower, or in line with revenue?",
            "Is growth consistent or lumpy?",
        ],
        "observation": obs,
        "beginner_tip": (
            "Revenue growing while profit is shrinking is a yellow flag — costs are "
            "rising faster than sales."
        ),
    }


def _step3_profitability(state: ResearchState) -> dict[str, Any]:
    f = state.fundamentals or {}
    roe = _to_pct(f.get("return_on_equity"))
    margin = _to_pct(f.get("profit_margin"))
    bits: list[str] = []
    if roe is not None:
        bits.append(f"ROE is {roe:.1f}% (>15% is generally considered healthy).")
    if margin is not None:
        bits.append(f"Profit margin is {margin:.1f}%.")
    obs = " ".join(bits) if bits else "Profitability ratios were not available."
    return {
        "step": 3,
        "title": "Check profitability",
        "questions": [
            "Are profit margins healthy?",
            "Is Return on Equity (ROE) good — does the company make good money on shareholder funds?",
            "Are margins improving or compressing over time?",
        ],
        "observation": obs,
        "beginner_tip": (
            "ROE below 10% is roughly the return on a fixed deposit — taking equity risk "
            "for that is rarely worth it unless you expect big improvements."
        ),
    }


def _step4_debt(state: ResearchState) -> dict[str, Any]:
    f = state.fundamentals or {}
    de = f.get("debt_to_equity")
    cr = f.get("current_ratio")
    bits: list[str] = []
    if de is not None:
        bits.append(f"Debt-to-Equity is {de:.0f}.")
    if cr is not None:
        bits.append(f"Current ratio is {cr:.2f} (>1 = short-term assets cover short-term liabilities).")
    obs = " ".join(bits) if bits else "Leverage ratios were not available."
    return {
        "step": 4,
        "title": "Check debt and risk",
        "questions": [
            "How much debt does the company carry vs equity?",
            "Can it pay interest comfortably from operating profit?",
            "Are short-term assets larger than short-term liabilities?",
        ],
        "observation": obs,
        "beginner_tip": (
            "Debt amplifies both returns and losses. A debt-heavy company in a rising-rate "
            "environment is a riskier bet than the same company would be in a falling-rate one."
        ),
    }


def _step5_valuation(state: ResearchState) -> dict[str, Any]:
    f = state.fundamentals or {}
    pe = f.get("trailing_pe")
    fpe = f.get("forward_pe")
    pb = f.get("price_to_book")
    bits: list[str] = []
    if pe is not None:
        bits.append(f"Trailing P/E is {pe:.1f}.")
    if fpe is not None:
        bits.append(f"Forward P/E is {fpe:.1f}.")
    if pb is not None:
        bits.append(f"Price-to-Book is {pb:.1f}.")
    obs = " ".join(bits) if bits else "Valuation ratios were not available."
    return {
        "step": 5,
        "title": "Check valuation",
        "questions": [
            "Is the stock expensive or cheap relative to its earnings (P/E)?",
            "How does P/E compare to the industry and to the company's own history?",
            "Does the price assume strong future growth?",
        ],
        "observation": obs,
        "beginner_tip": (
            "P/E in isolation is meaningless. A 50 P/E may be fine for a fast-growing tech "
            "company but a red flag for a slow-growing utility. Always compare with peers."
        ),
    }


def _step6_trend(state: ResearchState) -> dict[str, Any]:
    snap = state.indicators
    bits: list[str] = []
    bits.append(f"Trend is **{state.trend}**.")
    if snap.last_close is not None and snap.sma50 is not None:
        rel = "above" if snap.last_close > snap.sma50 else "below"
        bits.append(f"Price is {rel} the 50-day average.")
    if snap.rsi14 is not None:
        rsi_state = "overbought" if snap.rsi14 > 70 else "oversold" if snap.rsi14 < 30 else "neutral"
        bits.append(f"RSI is {snap.rsi14:.0f} ({rsi_state}).")
    if snap.macd_hist is not None:
        macd_state = "buyers stronger" if snap.macd_hist > 0 else "sellers stronger"
        bits.append(f"MACD momentum: {macd_state}.")
    obs = " ".join(bits)
    return {
        "step": 6,
        "title": "Check the price trend",
        "questions": [
            "Is the chart in an uptrend, downtrend, or sideways?",
            "Is momentum (MACD) supporting the trend or fading?",
            "Is the stock overbought (RSI > 70) or oversold (RSI < 30)?",
        ],
        "observation": obs,
        "beginner_tip": (
            "A great fundamental story with a broken chart often means the market knows "
            "something you don't. Don't ignore the chart even if you're a fundamentals person."
        ),
    }


def _step7_news(state: ResearchState) -> dict[str, Any]:
    n = len(state.developments)
    bits: list[str] = []
    if n == 0:
        bits.append("No company-specific events surfaced in this run.")
    else:
        bull = sum(1 for ev in state.developments if ev.polarity == "bullish")
        bear = sum(1 for ev in state.developments if ev.polarity == "bearish")
        bits.append(f"{n} ranked events: {bull} positive, {bear} negative, {n-bull-bear} neutral.")
        top = state.developments[0]
        bits.append(f"Top item: \"{top.title}\" — {top.source or 'unknown source'}.")
    obs = " ".join(bits)
    return {
        "step": 7,
        "title": "Check news and sentiment",
        "questions": [
            "Has there been a regulatory or legal event?",
            "Is there earnings news or guidance change?",
            "Are analyst ratings moving up or down?",
            "Is the news flow specific to the company or just sector noise?",
        ],
        "observation": obs,
        "beginner_tip": (
            "One bad headline rarely matters. Three bad headlines about the same theme over "
            "a few weeks is a story worth taking seriously."
        ),
    }


def _step8_summary(state: ResearchState) -> dict[str, Any]:
    """Final educational summary — reads like an analyst's notebook, NOT advice."""
    looks_good: list[str] = []
    looks_risky: list[str] = []
    needs_research: list[str] = []

    f = state.fundamentals or {}

    roe = _to_pct(f.get("return_on_equity"))
    if roe is not None:
        if roe >= 18:
            looks_good.append(f"Strong return on equity ({roe:.0f}%).")
        elif roe < 8:
            looks_risky.append(f"ROE is low ({roe:.0f}%) — capital is not being deployed efficiently.")

    rg = _to_pct(f.get("revenue_growth"))
    if rg is not None:
        if rg >= 15:
            looks_good.append(f"Revenue growth is healthy ({rg:+.0f}%).")
        elif rg < 0:
            looks_risky.append(f"Revenue is declining ({rg:+.0f}%).")

    de = f.get("debt_to_equity")
    if de is not None:
        if de >= 150:
            looks_risky.append(f"Debt-to-Equity is high ({de:.0f}).")
        elif de <= 30:
            looks_good.append(f"Balance sheet is conservative (D/E {de:.0f}).")

    pe = f.get("trailing_pe")
    if pe is not None:
        if pe > 50:
            looks_risky.append(f"P/E ({pe:.0f}) is rich — leaves little room for misses.")
        elif pe < 12:
            needs_research.append(f"P/E ({pe:.0f}) looks low — investigate whether it's value or a value trap.")

    if state.trend == "uptrend":
        looks_good.append("Chart is in an uptrend.")
    elif state.trend == "downtrend":
        looks_risky.append("Chart is in a downtrend.")

    if state.risk.regulatory_event:
        looks_risky.append("A regulatory event is on the record — read the original order before forming a view.")

    if not state.developments:
        needs_research.append("News flow was thin — read the latest annual report and quarterly call transcript directly.")

    if not f:
        needs_research.append("Fundamentals were unavailable from the public feed — pull the latest balance sheet directly.")

    return {
        "step": 8,
        "title": "Final learning summary",
        "questions": [
            "What looks good?",
            "What looks risky?",
            "What needs more research?",
            "What can a beginner learn from THIS specific case?",
        ],
        "looks_good": looks_good or ["No clearly positive standouts in the available data."],
        "looks_risky": looks_risky or ["No clearly negative standouts in the available data."],
        "needs_research": needs_research or ["No glaring data gaps — but always cross-check with the company's annual report."],
        "beginner_lesson": (
            "Notice how this single ticker requires checking the **business**, **growth**, "
            "**profitability**, **debt**, **valuation**, **chart**, and **news** before "
            "forming any view — and even then the answer is usually 'this is what's good, "
            "this is what's risky, here's what I'd study next.' That is what professionals "
            "actually do. They don't decide in 30 seconds."
        ),
        "compliance_note": (
            "This is educational content. It is not investment advice. Nothing here "
            "tells you to buy, sell, hold, or set a price target. Always consult a "
            "SEBI-registered financial advisor before making investment decisions."
        ),
    }


def build_analyst_workflow(state: ResearchState) -> list[dict[str, Any]]:
    return [
        _step1_business(state),
        _step2_growth(state),
        _step3_profitability(state),
        _step4_debt(state),
        _step5_valuation(state),
        _step6_trend(state),
        _step7_news(state),
        _step8_summary(state),
    ]
