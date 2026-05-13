"""Output schemas — deterministic stance + LLM explanation."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ConfidenceLabel = Literal["Low", "Medium", "High"]
TrendLabel = Literal["uptrend", "downtrend", "sideways", "unclear"]

# Deterministic stance enum — set by the rules engine, NOT by the LLM.
StanceLabel = Literal[
    "watch",
    "research_more",
    "early_positive_setup",
    "wait_for_confirmation",
    "avoid_for_now",
]

# Event categories used by the extractor + ranker + stance engine.
EventCategory = Literal[
    "regulatory",   # SEBI / RBI / IRDAI / SAT — ban, fine, probe, notice
    "legal",        # CBI / ED / SFIO / lawsuit / fraud / arrest
    "earnings",     # results / revenue / profit / beat / miss / guidance
    "rating",       # credit rating / analyst upgrade or downgrade
    "leadership",   # CEO / CFO / MD / board / resignation / appointment
    "corporate",    # merger / acquisition / demerger / delisting / buyback
    "product",      # launches / orders / contracts / plants / approvals
    "macro",        # generic market / sector news (low signal for ticker)
    "other",
]


# ---------------------------------------------------------------------------
# Market snapshot

class IndicatorSnapshot(BaseModel):
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_mid: Optional[float] = None
    atr14: Optional[float] = None
    volume_trend: Optional[str] = None  # "rising" | "falling" | "flat"
    last_close: Optional[float] = None


class SentimentSummary(BaseModel):
    score: float = 0.0  # -1.0 .. 1.0
    label: Literal["bullish", "bearish", "neutral", "mixed", "insufficient"] = "insufficient"
    n_headlines: int = 0
    n_articles: int = 0
    n_transcripts: int = 0
    notes: str = ""


class RiskFlags(BaseModel):
    elevated_volatility: bool = False
    bearish_momentum: bool = False
    conflicting_signals: bool = False
    weak_coverage: bool = False
    stale_data: bool = False
    regulatory_event: bool = False
    details: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recent developments (structured, deterministic)

class DevelopmentEvent(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)
    category: EventCategory = "other"
    polarity: Literal["bullish", "bearish", "neutral"] = "neutral"
    importance: int = 1            # 1 (low) .. 5 (critical)
    title: str = ""
    snippet: str = ""
    source: str = ""
    published: str = ""
    ticker_match: float = 0.0      # 0..1  how directly it mentions the ticker/company
    age_days: Optional[float] = None


# ---------------------------------------------------------------------------
# Deterministic stance

class StanceDecision(BaseModel):
    label: StanceLabel = "watch"
    score: float = 0.0             # -1 (bearish) .. +1 (bullish); 0 = neutral/uncertain
    reasons: list[str] = Field(default_factory=list)
    bull_points: list[str] = Field(default_factory=list)   # each ends with [ref: ...]
    bear_points: list[str] = Field(default_factory=list)
    what_changes_view: list[str] = Field(default_factory=list)
    used_evidence_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM explanation (no decisions!)

class LLMExplanation(BaseModel):
    """The LLM's job: EXPLAIN the deterministic stance + structured events.
    It MUST NOT pick a different stance or invent facts.
    """
    company_overview: str = ""           # what the company does (from evidence/meta only)
    chart_plain_english: str = ""        # what the price chart is showing
    recent_changes: str = ""             # narrative of what changed, refs events
    sources_say: str = ""                # what articles / transcripts are saying
    bull_case_text: str = ""             # narrative bull case
    bear_case_text: str = ""             # narrative bear case
    risks_text: str = ""                 # beginner-friendly risk narrative
    stance_explanation: str = ""         # explain the FIXED deterministic stance
    cited_evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified state

class ResearchState(BaseModel):
    ticker: str
    timeframe: str

    # Market
    company_meta: dict[str, Any] = Field(default_factory=dict)
    price_series_summary: dict[str, Any] = Field(default_factory=dict)
    indicators: IndicatorSnapshot = Field(default_factory=IndicatorSnapshot)
    trend: TrendLabel = "unclear"
    ohlcv: list[dict[str, Any]] = Field(default_factory=list)   # for candlestick detection

    # Content
    headlines: list[dict[str, Any]] = Field(default_factory=list)
    articles: list[dict[str, Any]] = Field(default_factory=list)
    transcripts: list[dict[str, Any]] = Field(default_factory=list)
    chart_notes: Optional[dict[str, Any]] = None

    # Analytics
    sentiment: SentimentSummary = Field(default_factory=SentimentSummary)
    confidence: ConfidenceLabel = "Low"
    confidence_score: float = 0.0
    risk: RiskFlags = Field(default_factory=RiskFlags)

    # Structured recent developments (deterministic)
    developments: list[DevelopmentEvent] = Field(default_factory=list)

    # Forward-looking calendar (earnings, ex-div, payment, splits) — same data
    # Zerodha / Groww surface, fetched from public yfinance/NSE sources.
    upcoming_events: list[dict[str, Any]] = Field(default_factory=list)

    # Fundamentals snapshot — P/E, ROE, debt/equity, dividend yield, etc.
    fundamentals: dict[str, Any] = Field(default_factory=dict)

    # Deterministic stance (decision is made HERE, not by the LLM)
    stance: StanceDecision = Field(default_factory=StanceDecision)

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # Missing data
    missing: list[str] = Field(default_factory=list)

    # LLM output — explanation only
    llm: Optional[LLMExplanation] = None


# ---------------------------------------------------------------------------
# Candlestick learning mode

class CandleDetection(BaseModel):
    pattern: str                     # e.g. "hammer", "bullish_engulfing"
    index: int                       # bar index in the supplied OHLCV
    date: str = ""
    bias: Literal["bullish", "bearish", "neutral"] = "neutral"
    confidence: float = 0.0          # 0..1 how textbook the match is
    note: str = ""                   # one-liner explaining THIS occurrence


class LearningLesson(BaseModel):
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    timeframe: Optional[str] = None
    lesson_sections: list[dict[str, Any]] = Field(default_factory=list)
    detections: list[CandleDetection] = Field(default_factory=list)
    last_close: Optional[float] = None
    n_bars: int = 0
    # The actual OHLCV bars used to produce the detections, so the UI can
    # render a candlestick chart and annotate it with the pattern markers.
    ohlcv: list[dict[str, Any]] = Field(default_factory=list)
    # Plain-English narration of the chart shape (trend, swings, volume drift)
    # — produced deterministically, no LLM.
    chart_summary: str = ""
