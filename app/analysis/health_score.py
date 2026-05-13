"""Educational Financial Health Scorecard — NOT a buy/sell signal.

Turns the existing fundamentals + indicators + sentiment into 7 category
labels with beginner-friendly verdicts. Output strictly avoids
buy/sell/target language — the goal is to teach a beginner WHICH dimensions
look strong/weak so they know where to study deeper.
"""

from __future__ import annotations

from typing import Any

from app.schemas.output import (
    IndicatorSnapshot,
    ResearchState,
    SentimentSummary,
)


# Category labels (educational, never directional)
LABEL_STRONG = "Strong"
LABEL_MODERATE = "Moderate"
LABEL_WEAK = "Weak"
LABEL_NEEDS_ATTENTION = "Needs Attention"
LABEL_INSUFFICIENT = "Insufficient Data"


def _to_pct(v: float | None) -> float | None:
    """yfinance is inconsistent — sometimes ratios are 0.18 (=18%), sometimes 18.0."""
    if v is None:
        return None
    try:
        f = float(v)
        if abs(f) <= 1.5:
            return f * 100.0
        return f
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-category scorers — each returns (label, plain-English finding)

def _score_growth(fund: dict[str, Any]) -> tuple[str, str]:
    rg = _to_pct(fund.get("revenue_growth"))
    eg = _to_pct(fund.get("earnings_growth"))
    if rg is None and eg is None:
        return LABEL_INSUFFICIENT, "Growth numbers were not available from the data feed."
    bits = []
    if rg is not None:
        bits.append(f"Revenue is changing {rg:+.1f}% year-over-year.")
    if eg is not None:
        bits.append(f"Earnings are changing {eg:+.1f}% year-over-year.")
    avg = ((rg or 0) + (eg or 0)) / max(1, sum(x is not None for x in (rg, eg)))
    if avg >= 15:
        return LABEL_STRONG, "Growth is improving. " + " ".join(bits)
    if avg >= 5:
        return LABEL_MODERATE, "Growth is positive but not exceptional. " + " ".join(bits)
    if avg >= 0:
        return LABEL_WEAK, "Growth is flat-ish. " + " ".join(bits)
    return LABEL_NEEDS_ATTENTION, "Growth has turned negative. " + " ".join(bits)


def _score_profitability(fund: dict[str, Any]) -> tuple[str, str]:
    roe = _to_pct(fund.get("return_on_equity"))
    margin = _to_pct(fund.get("profit_margin"))
    if roe is None and margin is None:
        return LABEL_INSUFFICIENT, "Profitability ratios were not available."
    bits = []
    if roe is not None:
        bits.append(f"ROE is {roe:.1f}% (profit on shareholder money).")
    if margin is not None:
        bits.append(f"Profit margin is {margin:.1f}%.")
    score = 0
    if roe is not None:
        score += 2 if roe >= 18 else 1 if roe >= 12 else 0
    if margin is not None:
        score += 2 if margin >= 15 else 1 if margin >= 7 else 0
    if score >= 3:
        return LABEL_STRONG, "Looks profitable. " + " ".join(bits)
    if score >= 2:
        return LABEL_MODERATE, "Profitability is okay. " + " ".join(bits)
    if score >= 1:
        return LABEL_WEAK, "Profitability is below comfortable levels. " + " ".join(bits)
    return LABEL_NEEDS_ATTENTION, "Profitability is thin. " + " ".join(bits)


def _score_valuation(fund: dict[str, Any]) -> tuple[str, str]:
    pe = fund.get("trailing_pe")
    pb = fund.get("price_to_book")
    if pe is None and pb is None:
        return LABEL_INSUFFICIENT, "Valuation ratios were not available."
    bits = []
    if pe is not None:
        bits.append(f"Trailing P/E is {pe:.1f}.")
    if pb is not None:
        bits.append(f"Price-to-Book is {pb:.1f}.")
    # pe ranges: <12 cheap, 12-25 normal, 25-40 rich, >40 very rich
    label = LABEL_MODERATE
    verdict = "Valuation is in a normal range."
    if pe is not None:
        if pe > 60:
            label, verdict = LABEL_NEEDS_ATTENTION, "Valuation looks very expensive — large growth needs to materialise to justify it."
        elif pe > 35:
            label, verdict = LABEL_WEAK, "Valuation looks expensive."
        elif pe < 10:
            label, verdict = LABEL_STRONG, "Valuation looks cheap — but cheap can also mean weak prospects."
    return label, verdict + " " + " ".join(bits)


def _score_debt_risk(fund: dict[str, Any]) -> tuple[str, str]:
    de = fund.get("debt_to_equity")
    cr = fund.get("current_ratio")
    if de is None and cr is None:
        return LABEL_INSUFFICIENT, "Leverage ratios were not available."
    bits = []
    if de is not None:
        bits.append(f"Debt-to-Equity is {de:.0f}.")
    if cr is not None:
        bits.append(f"Current ratio is {cr:.2f}.")
    if de is None:
        return LABEL_MODERATE, "Could not assess debt directly. " + " ".join(bits)
    if de >= 200:
        return LABEL_NEEDS_ATTENTION, "Debt level is very high — interest-rate sensitivity is real. " + " ".join(bits)
    if de >= 100:
        return LABEL_WEAK, "Debt is on the high side — needs a closer look. " + " ".join(bits)
    if de >= 40:
        return LABEL_MODERATE, "Debt is manageable. " + " ".join(bits)
    return LABEL_STRONG, "Balance sheet is conservative. " + " ".join(bits)


def _score_cash_flow(fund: dict[str, Any]) -> tuple[str, str]:
    """yfinance gives us payout ratio + dividend yield as a proxy for cash quality.
    A company that pays dividends usually has positive operating cash flow.
    """
    payout = _to_pct(fund.get("payout_ratio"))
    dy = _to_pct(fund.get("dividend_yield"))
    if payout is None and dy is None:
        return LABEL_INSUFFICIENT, "Cash flow signals were not available."
    bits = []
    if payout is not None:
        bits.append(f"Payout ratio is {payout:.0f}% of profit.")
    if dy is not None:
        bits.append(f"Dividend yield is ~{dy:.2f}%.")
    if payout is not None and payout > 90:
        return LABEL_WEAK, "Almost all profit is paid out — limited room to reinvest. " + " ".join(bits)
    if dy is not None and dy >= 2.5:
        return LABEL_STRONG, "Pays a meaningful dividend, suggesting healthy cash generation. " + " ".join(bits)
    if dy is not None and dy < 0.3:
        return LABEL_MODERATE, "No meaningful dividend — common for growth-stage companies. " + " ".join(bits)
    return LABEL_MODERATE, "Cash flow signals are unremarkable. " + " ".join(bits)


def _score_price_trend(snap: IndicatorSnapshot, trend: str) -> tuple[str, str]:
    if snap.last_close is None or snap.sma50 is None:
        return LABEL_INSUFFICIENT, "Not enough price data to assess the trend."
    above_sma = snap.last_close > snap.sma50
    macd_pos = (snap.macd_hist or 0) > 0
    rsi = snap.rsi14
    bits = [
        f"Trend label is {trend}.",
        f"Price is {'above' if above_sma else 'below'} the 50-day average.",
    ]
    if rsi is not None:
        bits.append(f"RSI is {rsi:.0f}.")
    if trend == "uptrend" and above_sma and macd_pos and (rsi or 50) < 70:
        return LABEL_STRONG, "Chart shows clean upward momentum. " + " ".join(bits)
    if trend == "downtrend" or (not above_sma and not macd_pos):
        return LABEL_NEEDS_ATTENTION, "Chart is leaning bearish. " + " ".join(bits)
    if rsi is not None and rsi > 75:
        return LABEL_WEAK, "Chart is in an uptrend but stretched — overbought. " + " ".join(bits)
    return LABEL_MODERATE, "Chart shows mixed momentum. " + " ".join(bits)


def _score_sentiment(sent: SentimentSummary) -> tuple[str, str]:
    if sent.label == "insufficient" or (sent.n_headlines + sent.n_articles) < 3:
        return LABEL_INSUFFICIENT, f"Only {sent.n_headlines} headlines were available — not enough to read sentiment."
    bits = [f"Sentiment label is {sent.label}, score {sent.score:+.2f} from {sent.n_headlines} items."]
    if sent.label == "bullish":
        return LABEL_STRONG, "Recent news tone is positive. " + " ".join(bits)
    if sent.label == "bearish":
        return LABEL_NEEDS_ATTENTION, "Recent news tone is negative. " + " ".join(bits)
    return LABEL_MODERATE, "Recent news tone is mixed/neutral. " + " ".join(bits)


# ---------------------------------------------------------------------------
# Public API

def build_health_scorecard(state: ResearchState) -> list[dict[str, Any]]:
    """Return a list of category dicts ready for the UI."""
    fund = state.fundamentals or {}
    cards: list[dict[str, Any]] = []

    def _add(name: str, why_pros_care: str, label_fn):
        label, finding = label_fn()
        cards.append({
            "name": name,
            "label": label,
            "finding": finding,
            "why_pros_care": why_pros_care,
        })

    _add(
        "Growth",
        "Growth shows whether the business is expanding or shrinking. A great company in a shrinking business is still a tough investment.",
        lambda: _score_growth(fund),
    )
    _add(
        "Profitability",
        "Profitability tells you whether the company actually makes money on what it sells. Revenue without profit is just busy work.",
        lambda: _score_profitability(fund),
    )
    _add(
        "Valuation",
        "Valuation answers the question 'how much are investors paying for ₹1 of this company?'. A great business at a terrible price can still be a bad investment.",
        lambda: _score_valuation(fund),
    )
    _add(
        "Debt Risk",
        "High debt can magnify returns — but also losses. When interest rates rise, debt-heavy companies are hit harder.",
        lambda: _score_debt_risk(fund),
    )
    _add(
        "Cash Flow Quality",
        "Profit on paper isn't the same as cash in the bank. Cash flow is what funds growth, dividends, and survival in tough times.",
        lambda: _score_cash_flow(fund),
    )
    _add(
        "Price Trend",
        "The market often knows things before headlines do. Trend tells you whether other investors are warming up or cooling on this name.",
        lambda: _score_price_trend(state.indicators, state.trend),
    )
    _add(
        "News Sentiment",
        "News doesn't move stocks alone, but recurring negatives (regulatory, fraud, earnings misses) are often the start of a longer story.",
        lambda: _score_sentiment(state.sentiment),
    )
    return cards
