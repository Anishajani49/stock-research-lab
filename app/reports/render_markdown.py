"""Analysis-mode Markdown report — 10 required sections, beginner-first.

Section layout (per the refactor spec):
  1.  What the company does
  2.  What the chart is showing
  3.  What changed recently
  4.  What articles / transcripts are saying
  5.  Bull case
  6.  Bear case
  7.  Main risks
  8.  Leaning now (one of 5)
  9.  Why this leaning was chosen
  10. What would change the view
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.analysis.stance import STANCE_PRETTY
from app.config import settings
from app.schemas.output import ResearchState


DISCLAIMER = (
    "This is a research assistant, not financial advice. "
    "Information is compiled from public Indian market sources (NSE/BSE/AMFI/news feeds) "
    "and may be incomplete or out of date. "
    "Markets are subject to risk; past performance does not guarantee future results. "
    "Always consult a **SEBI-registered financial advisor** before making investment decisions."
)


GLOSSARY = [
    ("Trend", "The general direction of the price — up, down, or sideways."),
    ("SMA", "Simple Moving Average. Average price over a window (e.g. SMA50 = last 50 days). Price above its SMA usually means recent momentum is positive."),
    ("RSI", "Relative Strength Index. 0–100 score of how heavily the stock has been bought or sold. Below 30 = heavily sold, above 70 = heavily bought."),
    ("MACD histogram", "Momentum indicator. Positive = buying pressure. Negative = selling pressure."),
    ("ATR", "Average True Range — typical daily price movement. Higher = more volatile."),
    ("SEBI", "Securities and Exchange Board of India — the stock market regulator."),
    ("Evidence ID", "A short code like `new_abc123` that links a claim to a specific headline / article / transcript in the Sources table."),
]


# ---------------------------------------------------------------------------

def _currency_symbol(currency: str | None) -> str:
    if not currency:
        return "₹"
    return {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency.upper(), "")


def _fmt_num(v, digits: int = 2) -> str:
    try:
        if v is None:
            return "n/a"
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "n/a"


def _fmt_money(v, currency: str | None, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{_currency_symbol(currency)}{float(v):,.{digits}f}"
    except Exception:
        return "n/a"


def _fmt_market_cap_inr(v) -> str:
    if v is None:
        return "n/a"
    try:
        f = float(v)
        cr = f / 1e7
        if cr >= 1e5:
            return f"₹{cr/1e5:,.2f} lakh Cr"
        return f"₹{cr:,.0f} Cr"
    except Exception:
        return "n/a"


def _instrument_is_mf(state: ResearchState) -> bool:
    return (state.company_meta or {}).get("instrument_type") == "mutual_fund"


def _source_coverage(state: ResearchState) -> str:
    counts: dict[str, int] = {}
    for h in state.headlines:
        s = h.get("source") or "Unknown"
        counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "_no headlines_"
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return " · ".join(f"**{k}** ({v})" for k, v in ordered)


def _sources_table(state: ResearchState) -> str:
    lines = ["| Evidence ID | Outlet | Title | URL |", "|---|---|---|---|"]
    seen: set[str] = set()

    def _add(eid, kind, title, url):
        if not eid or eid in seen:
            return
        seen.add(eid)
        t = (title or "").replace("|", "/")[:140]
        lines.append(f"| `{eid}` | {kind} | {t} | {url or ''} |")

    for h in state.headlines:
        _add(h.get("evidence_id"), h.get("source") or "news", h.get("title"), h.get("url"))
    for a in state.articles:
        if a.get("ok"):
            _add(a.get("evidence_id"), a.get("source_domain") or "article",
                 a.get("title") or a.get("url"), a.get("final_url") or a.get("url"))
    for t in state.transcripts:
        if t.get("ok"):
            _add(t.get("evidence_id"), "youtube", f"Transcript {t.get('video_id','')}", t.get("url"))
    if state.chart_notes and state.chart_notes.get("ok"):
        _add(state.chart_notes.get("evidence_id"), "chart", "Chart OCR", None)

    if len(lines) == 2:
        return "_No sources available._"
    return "\n".join(lines)


def _header_block(state: ResearchState) -> str:
    meta = state.company_meta or {}
    ccy = meta.get("currency") or settings.DEFAULT_CURRENCY
    is_mf = _instrument_is_mf(state)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if is_mf:
        return (
            f"**Scheme:** `{state.ticker}`  |  **Timeframe:** {state.timeframe}  |  **Generated:** {generated_at}\n"
            f"**Name:** {meta.get('long_name') or state.ticker}  |  "
            f"**Fund house:** {meta.get('fund_house') or 'n/a'}\n"
            f"**Category:** {meta.get('scheme_category') or 'n/a'}  |  "
            f"**Type:** {meta.get('scheme_type') or 'n/a'}  |  "
            f"**Currency:** {ccy}"
        )

    exch = meta.get("exchange") or "n/a"
    yfs = meta.get("yf_symbol") or state.ticker
    return (
        f"**Ticker:** `{state.ticker}` (`{yfs}`)  |  **Exchange:** {exch}  |  "
        f"**Timeframe:** {state.timeframe}  |  **Generated:** {generated_at}\n"
        f"**Company:** {meta.get('long_name') or state.ticker}  |  "
        f"**Sector:** {meta.get('sector') or 'n/a'}  |  "
        f"**Industry:** {meta.get('industry') or 'n/a'}\n"
        f"**Market Cap:** {_fmt_market_cap_inr(meta.get('market_cap'))}  |  "
        f"**P/E:** {_fmt_num(meta.get('pe'))}  |  **Currency:** {ccy}"
    )


_CATEGORY_FRIENDLY: dict[str, tuple[str, str]] = {
    # category → (emoji + friendly label, one-line plain-English meaning)
    "regulatory": ("⚖️ Regulator action", "the market regulator (SEBI / RBI / govt) took an action"),
    "legal":      ("🚓 Legal / fraud",     "a court case, fraud probe, or arrest was reported"),
    "earnings":   ("📊 Earnings update",   "the company reported quarterly numbers or a results-related update"),
    "rating":     ("📈 Analyst rating",    "a brokerage upgraded or downgraded the stock"),
    "leadership": ("👤 Leadership change", "a top executive joined, left, or was reshuffled"),
    "corporate":  ("🏢 Corporate action",  "a merger, demerger, buyback, dividend, or split"),
    "product":    ("🧪 Business news",     "a new product, contract, plant, or partnership"),
    "macro":      ("🌍 Market-wide news",  "broader market / sector news, not specific to the company"),
    "other":      ("📰 General news",      "general coverage that mentions the company"),
}

_POLARITY_FRIENDLY: dict[str, str] = {
    "bullish":  "🟢 looks positive",
    "bearish":  "🔴 looks negative",
    "neutral":  "⚪ neutral",
}


def _developments_bullets(state: ResearchState, top: int = 6) -> str:
    items = state.developments[:top]
    if not items:
        return (
            "- _Nothing company-specific surfaced in this run — only general market coverage._\n"
            "- _Try again later, or pick a different timeframe — Indian outlets sometimes "
            "lag on smaller tickers._"
        )
    lines: list[str] = []
    for ev in items:
        cat_label, cat_meaning = _CATEGORY_FRIENDLY.get(
            ev.category, _CATEGORY_FRIENDLY["other"]
        )
        pol_label = _POLARITY_FRIENDLY.get(ev.polarity, "⚪ neutral")
        age = (
            "today" if ev.age_days is not None and ev.age_days < 1
            else f"{int(ev.age_days)} day{'s' if int(ev.age_days) != 1 else ''} ago"
            if ev.age_days is not None else ""
        )
        src = f"*{ev.source}*" if ev.source else "_unknown source_"
        # Friendly, multi-line bullet — the headline is the headline, the
        # meta line below it explains in plain English what kind of event it is.
        ref_tag = (
            f"<sub>evidence: `{', '.join(ev.evidence_ids)}`</sub>"
            if ev.evidence_ids else ""
        )
        lines.append(
            f"- **{ev.title}**  \n"
            f"  {cat_label} · {pol_label} · {src} · {age}  \n"
            f"  _Why we noticed: {cat_meaning}._  \n"
            f"  {ref_tag}"
        )
    return "\n".join(lines)


def _developments_plain_english(state: ResearchState, top: int = 6) -> str:
    """Build a real prose summary so the reader doesn't see headlines twice."""
    items = state.developments[:top]
    if not items:
        return ""
    bull = sum(1 for e in items if e.polarity == "bullish")
    bear = sum(1 for e in items if e.polarity == "bearish")
    neut = len(items) - bull - bear
    cats = {}
    for e in items:
        cats[e.category] = cats.get(e.category, 0) + 1
    cat_list = ", ".join(
        f"{n}× {_CATEGORY_FRIENDLY.get(c, _CATEGORY_FRIENDLY['other'])[0]}"
        for c, n in sorted(cats.items(), key=lambda kv: -kv[1])
    )
    mood = (
        "lean negative" if bear > bull else
        "lean positive" if bull > bear else
        "are mixed"
    )
    return (
        f"In plain English: out of the {len(items)} most-relevant items we found, "
        f"**{bull}** look positive, **{bear}** look negative, and **{neut}** are neutral. "
        f"They {mood}. Categories covered: {cat_list}."
    )


def _bull_points_md(state: ResearchState) -> str:
    pts = state.stance.bull_points
    if not pts:
        return "- No clearly bullish points surfaced in the evidence for this ticker."
    return "\n".join(f"- {p}" for p in pts)


def _bear_points_md(state: ResearchState) -> str:
    pts = state.stance.bear_points
    if not pts:
        return "- No clearly bearish points surfaced in the evidence for this ticker."
    return "\n".join(f"- {p}" for p in pts)


def _why_md(state: ResearchState) -> str:
    reasons = state.stance.reasons or []
    if not reasons:
        return "- (No reasons produced.)"
    return "\n".join(f"- {r}" for r in reasons)


_STANCE_BEGINNER: dict[str, str] = {
    "watch": (
        "**What this means for you:** nothing strong is pushing the stock "
        "either way right now. A beginner's job here is just to watch — wait "
        "for a clear story (good earnings, a bad regulatory event, a chart "
        "breakout) before doing anything. No action is itself a valid action."
    ),
    "research_more": (
        "**What this means for you:** the system didn't have enough information "
        "to form a confident view — either the news feed was thin, or the price "
        "data didn't come through. Don't act on what you see here. Read the "
        "company's most recent quarterly result and check at least 2–3 named "
        "outlets (ET / MoneyControl / Mint) before forming a view."
    ),
    "early_positive_setup": (
        "**What this means for you:** the price chart and the news flow are "
        "both pointing in a positive direction, but this is **early**, not a "
        "buy signal. A beginner should still wait for one more confirmation "
        "(another good quarter, a follow-through up-move on rising volume) and "
        "should never put in more than they can afford to lose."
    ),
    "wait_for_confirmation": (
        "**What this means for you:** the signals are **mixed** — one part of "
        "the picture (e.g. price) says one thing, another part (e.g. news, or "
        "momentum) says the opposite. The honest answer is: nobody knows yet. "
        "Wait for the next earnings or a clear news catalyst before deciding."
    ),
    "avoid_for_now": (
        "**What this means for you:** a specific bad event is on the record "
        "(e.g. a regulator action, a fraud probe, or a confirmed downtrend with "
        "negative momentum). Until that risk is clearly resolved, a beginner "
        "should stay away — the downside is concrete, the upside is hopeful."
    ),
}


def _beginner_block(state: ResearchState) -> str:
    return _STANCE_BEGINNER.get(state.stance.label, "")


def _top_story_block(state: ResearchState) -> str:
    """The single most important development, shown prominently at the top.

    We pick the highest-importance ticker-specific event (importance >= 3)
    over the most-recent items. If nothing qualifies, we show the chart's
    main move so the report still surfaces ONE concrete fact.
    """
    candidates = [
        ev for ev in state.developments
        if ev.ticker_match >= 0.6 and ev.importance >= 3
    ]
    if candidates:
        candidates.sort(key=lambda e: (e.importance, -e.age_days if e.age_days else 0), reverse=True)
        ev = candidates[0]
        cat_label, cat_meaning = _CATEGORY_FRIENDLY.get(
            ev.category, _CATEGORY_FRIENDLY["other"]
        )
        pol_label = _POLARITY_FRIENDLY.get(ev.polarity, "⚪ neutral")
        age = (
            "today" if ev.age_days is not None and ev.age_days < 1
            else f"{int(ev.age_days)} day{'s' if int(ev.age_days) != 1 else ''} ago"
            if ev.age_days is not None else "recently"
        )
        src = f"*{ev.source}*" if ev.source else "_unknown source_"
        ref = (
            f"<sub>evidence: `{', '.join(ev.evidence_ids)}`</sub>"
            if ev.evidence_ids else ""
        )
        return (
            f"### 🗞️ Top story\n\n"
            f"> **{ev.title}**  \n"
            f"> {cat_label} · {pol_label} · {src} · {age}  \n"
            f"> _{cat_meaning.capitalize()}._  \n"
            f"> {ref}"
        )

    # Fallback: surface the price move
    snap = state.indicators
    pct = (state.price_series_summary or {}).get("period_return_pct")
    if pct is not None and snap.last_close is not None:
        meta = state.company_meta or {}
        ccy = meta.get("currency") or settings.DEFAULT_CURRENCY
        direction = "up" if pct > 0 else "down" if pct < 0 else "flat"
        return (
            f"### 🗞️ Top story\n\n"
            f"> No major company-specific event surfaced — the most concrete thing "
            f"this run is the **price move itself**: {state.timeframe} "
            f"return is **{pct:+.1f}%** ({direction}) with last close at "
            f"**{_fmt_money(snap.last_close, ccy)}**.  \n"
            f"> _Translation: news flow is quiet for this ticker; the chart is doing the talking._"
        )
    return ""


_JARGON_TRANSLATIONS: list[tuple[str, str]] = [
    # (substring to look for, plain-English replacement appended in parentheses)
    ("SMA50",            "the 50-day average price"),
    ("50-day average",   "the 50-day average price"),
    ("MACD histogram",   "MACD = a momentum gauge; positive = buyers stronger, negative = sellers stronger"),
    ("MACD",             "MACD = a momentum gauge"),
    ("RSI",              "RSI = how heavily bought/sold; below 30 oversold, above 70 overbought"),
    ("ATR",              "ATR = how much the price typically swings in a day"),
    ("ticker-specific",  "specific to this company"),
]


def _translated_reasons(state: ResearchState) -> str:
    reasons = state.stance.reasons or []
    if not reasons:
        return ""
    out_lines: list[str] = []
    for r in reasons:
        added: list[str] = []
        for key, plain in _JARGON_TRANSLATIONS:
            if key in r and plain not in r:
                added.append(plain)
                break  # one gloss per line is enough
        if added:
            out_lines.append(f"- {r}  \n  _(Plain English: {added[0]}.)_")
        else:
            out_lines.append(f"- {r}")
    return "\n".join(out_lines)


def _change_view_md(state: ResearchState) -> str:
    items = state.stance.what_changes_view or []
    if not items:
        return "- (No update criteria produced.)"
    return "\n".join(f"- {x}" for x in items)


def _upcoming_events_block(state: ResearchState) -> str:
    """Render the forward calendar — earnings, ex-div, payment dates."""
    events = state.upcoming_events or []
    if not events:
        return (
            "_No upcoming corporate events were found in the public calendar. "
            "Major Indian companies usually announce results dates 1–2 weeks in advance — "
            "check again closer to the next quarter._"
        )
    icons = {
        "earnings":          "📊",
        "ex_dividend":       "💰",
        "dividend_payment":  "💵",
        "last_split":        "✂️",
    }
    lines = []
    for ev in events[:8]:
        days = ev.get("days_until")
        if days is None:
            when = ev.get("date") or ""
        elif days < 0:
            when = f"{ev.get('date')} ({abs(days)}d ago)"
        elif days == 0:
            when = f"{ev.get('date')} (**today**)"
        elif days == 1:
            when = f"{ev.get('date')} (**tomorrow**)"
        else:
            when = f"{ev.get('date')} (in **{days} days**)"
        icon = icons.get(ev.get("kind", ""), "📅")
        title = ev.get("title") or ev.get("kind", "event").replace("_", " ").title()
        note = ev.get("note") or ""
        lines.append(
            f"- {icon} **{title}** — {when}"
            + (f"  \n  _{note}_" if note else "")
        )
    return "\n".join(lines)


def _fundamentals_block(state: ResearchState) -> str:
    """Beginner-readable fundamentals snapshot — same headline numbers Zerodha/Groww show."""
    f = state.fundamentals or {}
    if not f or all(v is None for v in f.values()):
        return "_Fundamentals snapshot unavailable for this ticker._"

    def n(v, digits=2, suffix=""):
        if v is None:
            return "n/a"
        try:
            return f"{float(v):,.{digits}f}{suffix}"
        except Exception:
            return "n/a"

    def pct(v):
        if v is None:
            return "n/a"
        try:
            f_v = float(v)
            # yfinance returns ratios sometimes as 0.18 (=18%), sometimes 18.0
            if abs(f_v) <= 1.5:
                f_v *= 100.0
            return f"{f_v:.2f}%"
        except Exception:
            return "n/a"

    rows = [
        # (label, value, beginner-friendly meaning)
        ("Trailing P/E",       n(f.get("trailing_pe")),
            "What investors pay today per ₹1 of last year's profit. Higher = more optimism (or expensive)."),
        ("Forward P/E",        n(f.get("forward_pe")),
            "Same idea but using next year's expected profit."),
        ("Price-to-Book",      n(f.get("price_to_book")),
            "Price vs the company's book value (assets minus debts). >3 = priced rich vs assets."),
        ("Book value / share", n(f.get("book_value")),
            "Net assets per share. Useful sanity floor for valuation."),
        ("Dividend yield",     pct(f.get("dividend_yield")),
            "Cash you'd get every year as a % of today's share price."),
        ("Payout ratio",       pct(f.get("payout_ratio")),
            "% of profit paid out as dividend. Very high = limited reinvestment room."),
        ("Return on Equity (ROE)", pct(f.get("return_on_equity")),
            "How much profit the company makes on shareholders' money. >15% is generally healthy."),
        ("Debt-to-Equity",     n(f.get("debt_to_equity")),
            "How much debt vs shareholders' equity. Lower is safer; >100 may need a closer look."),
        ("Profit margin",      pct(f.get("profit_margin")),
            "Profit as a % of revenue. Higher is better."),
        ("Revenue growth",     pct(f.get("revenue_growth")),
            "Year-over-year revenue change."),
        ("Earnings growth",    pct(f.get("earnings_growth")),
            "Year-over-year profit change."),
        ("52-week high",       n(f.get("fifty_two_week_high")),
            "Highest price in the past year."),
        ("52-week low",        n(f.get("fifty_two_week_low")),
            "Lowest price in the past year."),
        ("Beta",               n(f.get("beta")),
            "Volatility vs the market. 1 = moves with market; >1 = swings more; <1 = swings less."),
    ]
    # Filter out rows where value is "n/a" to keep things tight
    rows = [r for r in rows if r[1] != "n/a"]
    if not rows:
        return "_Fundamentals snapshot unavailable for this ticker._"

    lines = ["| Metric | Value | What it means for a beginner |", "|---|---|---|"]
    for label, val, meaning in rows:
        lines.append(f"| **{label}** | {val} | {meaning} |")
    return "\n".join(lines)


def _fundamentals_takeaways(state: ResearchState) -> str:
    """One-paragraph plain-English read of the fundamentals."""
    f = state.fundamentals or {}
    if not f:
        return ""
    bits: list[str] = []

    # Valuation read
    pe = f.get("trailing_pe")
    if pe is not None:
        if pe < 12:
            bits.append(f"P/E of {pe:.1f} looks **cheap on the surface** — but cheap can mean either undervalued or weak growth.")
        elif pe > 40:
            bits.append(f"P/E of {pe:.1f} is **rich** — investors are pricing in strong future growth, leaves little room for misses.")
        else:
            bits.append(f"P/E of {pe:.1f} is in a **normal range**.")

    # ROE read
    roe = f.get("return_on_equity")
    if roe is not None:
        roe_pct = roe * 100 if abs(roe) <= 1.5 else roe
        if roe_pct >= 18:
            bits.append(f"ROE of ~{roe_pct:.0f}% is **strong** (the company makes good profit on shareholder money).")
        elif roe_pct <= 8:
            bits.append(f"ROE of ~{roe_pct:.0f}% is **weak** (lower than what bank fixed deposits return).")

    # Debt read
    de = f.get("debt_to_equity")
    if de is not None:
        if de >= 150:
            bits.append(f"Debt-to-Equity of {de:.0f} is **high** — the company runs on borrowed money; rising rates can hurt.")
        elif de <= 30:
            bits.append(f"Debt-to-Equity of {de:.0f} is **low** — balance sheet is conservative.")

    # Yield read
    dy = f.get("dividend_yield")
    if dy is not None:
        dy_pct = dy * 100 if abs(dy) <= 1.5 else dy
        if dy_pct >= 3:
            bits.append(f"Dividend yield of ~{dy_pct:.1f}% is **decent income** — close to a savings account, plus stock upside.")

    if not bits:
        return ""
    return "**Plain-English read:** " + " ".join(bits)


def _indicator_block(state: ResearchState) -> str:
    snap = state.indicators
    is_mf = _instrument_is_mf(state)
    lines = [
        f"- **Price vs SMA50:** {'above' if (snap.last_close and snap.sma50 and snap.last_close > snap.sma50) else 'below' if (snap.last_close and snap.sma50) else 'n/a'} "
        f"  _(above = recent momentum positive)_",
        f"- **RSI14:** {_fmt_num(snap.rsi14)}  _(<30 heavily sold · 30–70 normal · >70 heavily bought)_",
        f"- **MACD momentum:** {_fmt_num(snap.macd_hist, 4)}  _(+ buying pressure · − selling pressure)_",
    ]
    if not is_mf:
        lines.append(f"- **Volatility (ATR14):** {_fmt_num(snap.atr14)}  _(typical daily swing)_")
        lines.append(f"- **Volume trend:** {snap.volume_trend or 'n/a'}  _(rising volume = growing interest)_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def render(state: ResearchState) -> str:
    meta = state.company_meta or {}
    snap = state.indicators
    sent = state.sentiment
    risk = state.risk
    llm = state.llm
    ccy = meta.get("currency") or settings.DEFAULT_CURRENCY
    is_mf = _instrument_is_mf(state)

    stance_badge = STANCE_PRETTY.get(state.stance.label, state.stance.label)
    price_heading = "NAV behaviour" if is_mf else "What the chart is showing"
    price_label = "Last NAV" if is_mf else "Last close"

    missing_md = ""
    if state.missing:
        missing_md = "\n> ⚠️ **Missing data:** " + ", ".join(state.missing)

    glossary_md = "\n".join(f"- **{term}** — {defn}" for term, defn in GLOSSARY)

    # LLM-written narratives — fall back to deterministic summaries if absent
    company_overview = llm.company_overview if llm else ""
    chart_plain = llm.chart_plain_english if llm else ""
    recent_changes_narrative = llm.recent_changes if llm else ""
    sources_say = llm.sources_say if llm else ""
    bull_text = llm.bull_case_text if llm else ""
    bear_text = llm.bear_case_text if llm else ""
    risks_text = llm.risks_text if llm else ""
    stance_text = llm.stance_explanation if llm else ""

    cited = ", ".join(f"`{c}`" for c in (llm.cited_evidence if llm else [])) or "_(none)_"

    md = f"""# Research Report — {meta.get('long_name') or state.ticker}

{_header_block(state)}
{missing_md}

---

{_top_story_block(state)}

---

## 🎯 Bottom line

### {stance_badge}
Confidence: **{state.confidence}** ({state.confidence_score:.2f})

{_beginner_block(state)}

**Why the system landed here (in short):**

{_translated_reasons(state)}

{(f'_Analyst-model take:_ {stance_text}') if stance_text else ''}

---

## 1. 🏢 What the company does

{company_overview or f"{meta.get('long_name') or state.ticker} — Sector: {meta.get('sector') or 'n/a'}. Industry: {meta.get('industry') or 'n/a'}."}

---

## 2. 📈 {price_heading}

{chart_plain or '_No narrative produced._'}

**Snapshot**
- {price_label}: **{_fmt_money(snap.last_close, ccy)}**
- Period return: **{_fmt_num(state.price_series_summary.get('period_return_pct'))}%** over {state.timeframe}
- Period high / low: {_fmt_money(state.price_series_summary.get('period_high'), ccy)} / {_fmt_money(state.price_series_summary.get('period_low'), ccy)}
- Trend label: **{state.trend}**

**At-a-glance indicators**
{_indicator_block(state)}

---

## 3. 📰 What changed recently

> Below are the most relevant news items about this company in the recent
> period — automatically ranked by how closely they're about this ticker,
> how recent they are, and how serious they look.

{_developments_bullets(state)}

{_developments_plain_english(state)}

{(f'**Plain-English summary from the analyst model:** {recent_changes_narrative}') if recent_changes_narrative and not recent_changes_narrative.lstrip().startswith('•') and not recent_changes_narrative.lstrip().startswith('-') else ''}

**News coverage by outlet:** {_source_coverage(state)}

---

## 3a. 📅 Upcoming events (calendar)

> Forward-looking corporate events from the public calendar (the same data
> Zerodha and Groww show on their stock pages, fetched from yfinance).
> Knowing these dates is more useful than reacting after the fact.

{_upcoming_events_block(state)}

---

## 3b. 📊 Key fundamentals (the basics every beginner should check)

> These are the headline numbers that tell you whether the company is
> profitable, growing, expensive, and how much debt it carries.

{_fundamentals_block(state)}

{_fundamentals_takeaways(state)}

---

## 4. 🎙️ What articles / transcripts are saying

{sources_say or '_No narrative produced._'}

**Deterministic sentiment:** label = **{sent.label}**, score = {sent.score:+.3f}
({sent.n_headlines} headlines · {sent.n_articles} articles · {sent.n_transcripts} transcripts)

---

## 5. 🟢 Bull case

{bull_text or ''}

{_bull_points_md(state)}

---

## 6. 🔴 Bear case

{bear_text or ''}

{_bear_points_md(state)}

---

## 7. ⚠️ Main risks to be aware of

{risks_text or ''}

**Automatic risk checks:**
- Regulatory event: **{"yes" if risk.regulatory_event else "no"}**
- Elevated volatility: **{"yes" if risk.elevated_volatility else "no"}**
- Bearish momentum: **{"yes" if risk.bearish_momentum else "no"}**
- Conflicting signals: **{"yes" if risk.conflicting_signals else "no"}**
- Weak news coverage: **{"yes" if risk.weak_coverage else "no"}**
- Stale data: **{"yes" if risk.stale_data else "no"}**
{chr(10).join('- ' + d for d in risk.details) if risk.details else ''}

---

## 8. 🧭 Leaning now

### {stance_badge}

Possible leanings: `watch` · `research_more` · `early_positive_setup` · `wait_for_confirmation` · `avoid_for_now`.
This choice was made by a deterministic rules engine using price trend + momentum + news events + risk checks. The LLM does not change it.

---

## 9. 🧠 Why this leaning was chosen

{_beginner_block(state)}

**Reasons the rules engine fired (with plain-English glosses):**

{_translated_reasons(state)}

{(f'**Analyst-model explanation:** {stance_text}') if stance_text else ''}

---

## 10. 🔄 What would change this view

{_change_view_md(state)}

---

## 📊 Confidence

**{state.confidence}** (score {state.confidence_score:.2f}). Confidence reflects data completeness, freshness, and how well indicators and news agreed.

---

## 🔗 Sources

**Cited in the narrative:** {cited}

{_sources_table(state)}

---

## 📖 Glossary (jargon decoded)

{glossary_md}

---

## ⚖️ Disclaimer

{DISCLAIMER}
"""
    return md


def save_report(state: ResearchState, md: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_ticker = state.ticker.replace("/", "_")
    out = settings.PROCESSED_DIR / f"{safe_ticker}_{ts}.md"
    out.write_text(md, encoding="utf-8")
    return out
