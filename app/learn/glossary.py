"""Beginner finance dictionary — short, plain-English definitions.

Used by the /api/glossary endpoint and the searchable glossary page.
Each entry has:
  - term     : the word/phrase
  - aliases  : alternate spellings / abbreviations the search box should match
  - category : grouping for filters
  - meaning  : one-line beginner definition
  - why_it_matters : one-line plain-English reason a beginner should care
"""

from __future__ import annotations


GLOSSARY: list[dict[str, object]] = [
    # ---- Income & profit ----
    {
        "term": "Revenue",
        "aliases": ["sales", "top line", "turnover"],
        "category": "income",
        "meaning": "Total money the company brought in from selling its products or services.",
        "why_it_matters": "Without revenue growth, profit growth eventually stops. It's the 'top line' for a reason.",
    },
    {
        "term": "Profit",
        "aliases": ["net profit", "net income", "bottom line", "earnings"],
        "category": "income",
        "meaning": "What's left of revenue after the company pays all its costs, interest, and taxes.",
        "why_it_matters": "Revenue without profit is just busy work — profit is what the company can actually keep.",
    },
    {
        "term": "EPS (Earnings Per Share)",
        "aliases": ["eps", "earnings per share"],
        "category": "income",
        "meaning": "Profit divided by the number of shares — your slice of the company's profit per share you own.",
        "why_it_matters": "Comparing EPS over years tells you whether profit per share is actually growing.",
    },
    {
        "term": "Profit Margin",
        "aliases": ["margin", "net margin"],
        "category": "income",
        "meaning": "Profit as a percentage of revenue. Higher is better.",
        "why_it_matters": "Two companies with the same revenue but different margins are very different businesses.",
    },

    # ---- Valuation ----
    {
        "term": "P/E Ratio",
        "aliases": ["pe", "pe ratio", "price to earnings"],
        "category": "valuation",
        "meaning": "How much investors pay today for ₹1 of last year's profit.",
        "why_it_matters": "High P/E usually means the market expects strong growth ahead — but it also means less room for misses.",
    },
    {
        "term": "Forward P/E",
        "aliases": ["forward pe", "fpe"],
        "category": "valuation",
        "meaning": "P/E using analysts' expected NEXT year earnings instead of last year's.",
        "why_it_matters": "A more forward-looking valuation read — but only as good as the estimate.",
    },
    {
        "term": "Price-to-Book (P/B)",
        "aliases": ["pb", "price to book", "p/b"],
        "category": "valuation",
        "meaning": "Stock price compared to the company's book value (assets minus debts).",
        "why_it_matters": "P/B above 3 means you're paying well above accounting book value — you're paying for future expectations.",
    },
    {
        "term": "Market Cap",
        "aliases": ["market capitalization", "mcap"],
        "category": "valuation",
        "meaning": "Total value of all the company's shares — share price × number of shares.",
        "why_it_matters": "Tells you the size class of the company: small-cap, mid-cap, large-cap each behave differently.",
    },

    # ---- Quality / health ----
    {
        "term": "ROE (Return on Equity)",
        "aliases": ["roe", "return on equity"],
        "category": "quality",
        "meaning": "Profit the company makes for every ₹1 of shareholder money it uses.",
        "why_it_matters": "ROE > 15% is generally considered healthy. ROE near a fixed-deposit rate is a red flag.",
    },
    {
        "term": "ROCE (Return on Capital Employed)",
        "aliases": ["roce", "return on capital employed"],
        "category": "quality",
        "meaning": "Profit the company makes on ALL the capital it uses — equity AND debt.",
        "why_it_matters": "ROCE is harder to flatter than ROE because it includes debt. Many pros prefer it.",
    },
    {
        "term": "Debt-to-Equity",
        "aliases": ["d/e", "de", "debt to equity", "leverage"],
        "category": "quality",
        "meaning": "How much debt the company carries vs shareholder money.",
        "why_it_matters": "High D/E magnifies both gains and losses. Rising rates hit debt-heavy companies harder.",
    },
    {
        "term": "Free Cash Flow (FCF)",
        "aliases": ["fcf", "free cash flow"],
        "category": "quality",
        "meaning": "Cash left over after a company pays for operations and investments.",
        "why_it_matters": "Profit is on paper; FCF is real money. A profitable company with weak FCF often has accounting flatter.",
    },

    # ---- Ownership & flows ----
    {
        "term": "Promoter Holding",
        "aliases": ["promoter", "promoters"],
        "category": "ownership",
        "meaning": "Percentage of the company owned by its founders / controlling family.",
        "why_it_matters": "Rising promoter holding is usually positive (skin in the game). Falling holding via pledge or sale is a warning.",
    },
    {
        "term": "FII (Foreign Institutional Investors)",
        "aliases": ["fii", "fpi", "foreign institutional investors"],
        "category": "ownership",
        "meaning": "Large foreign investors (pension funds, hedge funds) buying or selling Indian stocks.",
        "why_it_matters": "FII flows can move the whole market for short periods, especially when the rupee or interest rates shift.",
    },
    {
        "term": "DII (Domestic Institutional Investors)",
        "aliases": ["dii", "domestic institutional investors"],
        "category": "ownership",
        "meaning": "Indian mutual funds, insurers, banks investing in Indian stocks.",
        "why_it_matters": "DII flows often counter-balance FIIs and have grown structurally as more Indians invest via SIPs.",
    },
    {
        "term": "Dividend",
        "aliases": ["dividend", "payout"],
        "category": "ownership",
        "meaning": "Cash the company pays out to shareholders from profit.",
        "why_it_matters": "A regular, growing dividend signals stable cash flow. A sudden dividend cut is a warning sign.",
    },

    # ---- Technicals ----
    {
        "term": "Moving Average (SMA)",
        "aliases": ["sma", "sma50", "sma200", "moving average"],
        "category": "technicals",
        "meaning": "Average closing price over a window (e.g. SMA50 = average of last 50 days).",
        "why_it_matters": "Price above its SMA50 means recent momentum is positive. Above SMA200 means longer-term trend is up.",
    },
    {
        "term": "RSI (Relative Strength Index)",
        "aliases": ["rsi", "rsi14"],
        "category": "technicals",
        "meaning": "0–100 score of how heavily the stock has been bought or sold recently.",
        "why_it_matters": "RSI < 30 = heavily sold (possible bounce). RSI > 70 = heavily bought (possible cool-off).",
    },
    {
        "term": "MACD",
        "aliases": ["macd", "macd histogram"],
        "category": "technicals",
        "meaning": "Momentum gauge built from two moving averages. Histogram > 0 = buyers stronger; < 0 = sellers stronger.",
        "why_it_matters": "MACD turning positive after being negative is a common 'momentum is shifting up' signal.",
    },
    {
        "term": "Support",
        "aliases": ["support level"],
        "category": "technicals",
        "meaning": "A price level where buyers have repeatedly stepped in to stop further declines.",
        "why_it_matters": "Breaking below support often means the next leg of the move is to lower support — until buyers reappear.",
    },
    {
        "term": "Resistance",
        "aliases": ["resistance level"],
        "category": "technicals",
        "meaning": "A price level where sellers have repeatedly stepped in to stop further rises.",
        "why_it_matters": "Breaking above resistance with rising volume is a common 'breakout' setup professionals watch for.",
    },
    {
        "term": "Volume",
        "aliases": ["volume", "trading volume"],
        "category": "technicals",
        "meaning": "Number of shares traded in a period.",
        "why_it_matters": "Big price moves on big volume are believed; big moves on tiny volume often reverse.",
    },
    {
        "term": "Volatility",
        "aliases": ["volatility", "atr", "beta"],
        "category": "technicals",
        "meaning": "How much the stock's price typically swings.",
        "why_it_matters": "More volatility = bigger possible gains AND bigger possible losses. Match it to your risk tolerance.",
    },

    # ---- Market language ----
    {
        "term": "Bullish",
        "aliases": ["bull", "bull market"],
        "category": "language",
        "meaning": "Expecting prices to rise.",
        "why_it_matters": "A 'bullish' analyst expects upside; a 'bull market' is a multi-year period of rising prices.",
    },
    {
        "term": "Bearish",
        "aliases": ["bear", "bear market"],
        "category": "language",
        "meaning": "Expecting prices to fall.",
        "why_it_matters": "A 'bearish' view doesn't always mean 'sell' — it can mean 'wait, don't add yet'.",
    },
    {
        "term": "Beta",
        "aliases": ["beta"],
        "category": "technicals",
        "meaning": "Volatility relative to the market. Beta 1 = moves with the market. >1 = swings more. <1 = swings less.",
        "why_it_matters": "High-beta stocks can outperform in bull markets and underperform badly in bear markets.",
    },
]


def get_glossary() -> list[dict[str, object]]:
    return GLOSSARY
