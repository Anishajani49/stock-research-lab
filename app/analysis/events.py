"""Deterministic event extractor — no LLM involved.

Given a list of headline dicts (with title/snippet/source/published/evidence_id)
and optionally a list of article dicts (with text), this module:

  1. Tags each item with an event category (regulatory / legal / earnings / …).
  2. Scores each item's polarity (bullish / bearish / neutral) using keyword cues.
  3. Estimates importance (1..5) based on the category + strength cues.
  4. Estimates ticker_match (0..1) from mentions of the ticker + company tokens.
  5. Computes age_days from the published timestamp.

The result is a list of DevelopmentEvent models, ready to be ranked and fed to
both the stance engine and the LLM prompt.

This file is deliberately keyword/regex-based so different tickers produce
different structured events — no generic LLM filler.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

from app.schemas.output import DevelopmentEvent, EventCategory

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword dictionaries (lowercase). Order matters — we assign the FIRST
# category that matches in priority order below.

_REGULATORY = [
    # Indian regulators
    r"\bsebi\b", r"\brbi\b", r"\birdai\b", r"\bsat\b", r"\bcci\b", r"\bnse\b.*\bsuspend",
    r"\bbse\b.*\bsuspend", r"\bpfr?da\b",
    # Actions
    r"\bban(ned|s)?\b", r"\bprohibit", r"\bprobe", r"\binquiry", r"\binvestigat",
    r"\bshow cause", r"\bpenalt", r"\bfine(d)?\b", r"\bnotice", r"\bsuspended\b",
    r"\bbarr(ed|ing)\b", r"\bcrackdown", r"\bdisgorge",
    # Specific industry bans (surfaces things like ITC / tobacco / pharma)
    r"\btobacco (ban|curb|rule|advisory|restriction)",
    r"\bexport ban\b", r"\bimport ban\b",
]

_LEGAL = [
    r"\bcbi\b", r"\benforcement directorate\b", r"\bed\b(?! times)", r"\bsfio\b",
    r"\bfraud", r"\bscam", r"\bmoney launder", r"\bforgery", r"\bembezzle",
    r"\blawsuit", r"\blitigation", r"\bsued\b", r"\bcourt\b", r"\bsupreme court",
    r"\bhigh court", r"\bnclt\b", r"\braid(ed|s)?\b", r"\barrest(ed)?\b",
    r"\bcharge(d|sheet)", r"\bfiling\b.*\bfraud",
]

_EARNINGS = [
    r"\bq[1-4]\b(?! fy)?", r"\bquarterly (result|report|earning)",
    r"\bresults\b", r"\bearnings\b", r"\bprofit", r"\brevenue", r"\brevenue\b",
    r"\bebitda", r"\bmargin(s)?\b", r"\bloss(es)?\b", r"\bbeat(s)? estimate",
    r"\bmiss(es|ed)? estimate", r"\bconsensus", r"\boutlook", r"\bguidance",
    r"\brevises?\s+guidance", r"\bcut(s)? (outlook|forecast|guidance)",
    r"\braises? (outlook|forecast|guidance)",
]

_RATING = [
    r"\bdowngrade", r"\bupgrade", r"\bcredit rating", r"\brating action",
    r"\bcrisil", r"\bicra", r"\bcare rating", r"\bmoody(?:'s)?\b",
    r"\bs&p\b", r"\bfitch\b", r"\btarget price", r"\bbuy rating", r"\bsell rating",
    r"\boutperform", r"\bunderperform", r"\breduce rating",
]

_LEADERSHIP = [
    r"\bceo\b", r"\bcfo\b", r"\bmanaging director\b", r"\bmd\b(?! &)",
    r"\bchairman\b", r"\bdirector\b", r"\bboard\b", r"\bresign", r"\bappoint",
    r"\bsteps? down", r"\bquits?\b", r"\binducts?\b",
]

_CORPORATE = [
    r"\bmerger", r"\bacquisition", r"\bacquires?\b", r"\bacquired\b",
    r"\bdemerger", r"\bdemerge", r"\bspin.?off", r"\bstake sale", r"\bstake buy",
    r"\bpreferential (allotment|issue)", r"\bipo\b", r"\bfpo\b",
    r"\brights issue", r"\bbuyback\b", r"\bbonus (issue|share)",
    r"\bstock split", r"\bdividend\b", r"\bdelist", r"\brelist",
    r"\binsolvency", r"\bibc\b", r"\bbankruptc",
]

_PRODUCT = [
    r"\bnew product", r"\blaunch(ed|es)?\b", r"\bunveil", r"\bdebut",
    r"\border win", r"\bbags order", r"\bcontract", r"\btender",
    r"\bplant\b", r"\bfactory\b", r"\bcapacity", r"\bexpansion",
    r"\bapproval\b", r"\bcdsco\b", r"\bfda\b",
]

_MACRO = [
    r"\bnifty", r"\bsensex", r"\bbse\b(?!.*suspend)", r"\bnse\b(?!.*suspend)",
    r"\bmarket(s)? (end|open|close)", r"\bfii\b", r"\bdii\b", r"\bforex",
    r"\brupee", r"\bbudget", r"\bmonetary policy", r"\binflation",
    r"\bcrude oil", r"\bgold\b.*\bprice", r"\binterest rate", r"\brepo rate",
]


_CATEGORY_PATTERNS: list[tuple[EventCategory, list[str]]] = [
    ("regulatory", _REGULATORY),
    ("legal",      _LEGAL),
    ("earnings",   _EARNINGS),
    ("rating",     _RATING),
    ("leadership", _LEADERSHIP),
    ("corporate",  _CORPORATE),
    ("product",    _PRODUCT),
    ("macro",      _MACRO),
]


# Words that push polarity (used in addition to category default)
_BEARISH_WORDS = [
    "ban", "banned", "probe", "fraud", "fine", "penalty", "downgrade",
    "loss", "miss", "misses", "cut", "slump", "plunge", "crash", "fall",
    "fell", "decline", "drop", "arrest", "raid", "resign", "resigns",
    "delist", "bankruptcy", "insolvency", "suspended", "recall",
    "lawsuit", "scam", "investigation", "warning", "show cause",
]

_BULLISH_WORDS = [
    "beat", "beats", "upgrade", "profit", "record", "all-time high",
    "surge", "jump", "rally", "rise", "rises", "gains", "gained",
    "approval", "order win", "bags order", "contract", "launches",
    "launch", "expansion", "bonus", "dividend", "acquires",
    "raises guidance", "raises outlook", "strong quarter",
]


# Category default polarity + importance (severity)
_CATEGORY_DEFAULTS: dict[EventCategory, dict[str, Any]] = {
    "regulatory": {"polarity": "bearish", "importance": 5},
    "legal":      {"polarity": "bearish", "importance": 5},
    "earnings":   {"polarity": "neutral", "importance": 4},
    "rating":     {"polarity": "neutral", "importance": 3},
    "leadership": {"polarity": "neutral", "importance": 3},
    "corporate":  {"polarity": "neutral", "importance": 3},
    "product":    {"polarity": "bullish", "importance": 2},
    "macro":      {"polarity": "neutral", "importance": 1},
    "other":      {"polarity": "neutral", "importance": 1},
}


# ---------------------------------------------------------------------------

def _first_match(text: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _classify_category(text: str) -> EventCategory:
    for cat, patterns in _CATEGORY_PATTERNS:
        if _first_match(text, patterns):
            return cat
    return "other"


def _score_polarity(text: str, category: EventCategory) -> tuple[str, int]:
    """Return (polarity, adjusted_importance)."""
    low = text.lower()
    bull = sum(1 for w in _BULLISH_WORDS if w in low)
    bear = sum(1 for w in _BEARISH_WORDS if w in low)

    default = _CATEGORY_DEFAULTS.get(category, _CATEGORY_DEFAULTS["other"])
    polarity = default["polarity"]
    importance = int(default["importance"])

    if bear > bull and bear >= 1:
        polarity = "bearish"
        importance = min(5, importance + (1 if bear >= 2 else 0))
    elif bull > bear and bull >= 1:
        polarity = "bullish"
        importance = min(5, importance + (1 if bull >= 2 else 0))
    # tie -> keep category default
    return polarity, importance


def _ticker_tokens(ticker: str, company_name: str | None) -> list[str]:
    toks: list[str] = []
    bare = re.sub(r"\.(NS|BO)$", "", ticker.strip().upper(), flags=re.I)
    toks.append(bare.lower())
    if company_name:
        for piece in re.split(r"[\s\-]+", company_name.lower()):
            piece = re.sub(r"[^a-z0-9]", "", piece)
            # skip generic suffixes and short tokens
            if piece in {"ltd", "limited", "corp", "corporation", "inc",
                         "the", "and", "of", "co", "company", "plc"}:
                continue
            if len(piece) >= 4:
                toks.append(piece)
    # dedupe, keep order
    seen: set[str] = set()
    out: list[str] = []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:5]


def _score_ticker_match(text: str, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    low = text.lower()
    # exact bare-ticker word-boundary match → max
    if re.search(rf"\b{re.escape(tokens[0])}\b", low):
        return 1.0
    # any company token present
    hits = sum(1 for t in tokens[1:] if t and t in low)
    if hits >= 2:
        return 0.8
    if hits == 1:
        return 0.6
    return 0.0


def _compute_age_days(published: str | None) -> float | None:
    if not published:
        return None
    dt: datetime | None = None
    # Try RFC2822 first (feedparser gives this)
    try:
        dt = parsedate_to_datetime(published)
    except Exception:
        dt = None
    if dt is None:
        # Try ISO
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return round(delta.total_seconds() / 86400.0, 2)


# ---------------------------------------------------------------------------
# Public API

def extract_developments(
    headlines: Iterable[dict[str, Any]],
    articles: Iterable[dict[str, Any]] | None = None,
    ticker: str = "",
    company_name: str | None = None,
) -> list[DevelopmentEvent]:
    """Extract structured developments from headlines + articles.

    Each returned event already has polarity, importance, ticker_match, age_days.
    Caller (ranker / stance engine) decides priority.
    """
    tokens = _ticker_tokens(ticker, company_name)
    events: list[DevelopmentEvent] = []
    seen_titles: set[str] = set()

    # --- Headlines ---
    for h in headlines:
        title = (h.get("title") or "").strip()
        if not title:
            continue
        key = title.lower()[:120]
        if key in seen_titles:
            continue
        seen_titles.add(key)

        snippet = (h.get("snippet") or "").strip()
        text_for_match = f"{title}. {snippet}".lower()

        category = _classify_category(text_for_match)
        polarity, importance = _score_polarity(text_for_match, category)
        ticker_match = _score_ticker_match(text_for_match, tokens)
        age_days = _compute_age_days(h.get("published"))

        # Low ticker_match + macro category → downweight importance
        if category == "macro" and ticker_match < 0.5:
            importance = 1

        events.append(DevelopmentEvent(
            evidence_ids=[h.get("evidence_id")] if h.get("evidence_id") else [],
            category=category,
            polarity=polarity,  # type: ignore[arg-type]
            importance=importance,
            title=title[:240],
            snippet=snippet[:400],
            source=h.get("source") or "",
            published=h.get("published") or "",
            ticker_match=ticker_match,
            age_days=age_days,
        ))

    # --- Articles (upgrade matching headlines if we have a richer body) ---
    if articles:
        for a in articles:
            if not a.get("ok"):
                continue
            body = (a.get("text") or "")[:4000]
            title = (a.get("title") or a.get("url") or "").strip()
            if not body and not title:
                continue
            text_for_match = f"{title}. {body}".lower()
            category = _classify_category(text_for_match)
            polarity, importance = _score_polarity(text_for_match, category)
            ticker_match = _score_ticker_match(text_for_match, tokens)

            # Try to merge into an existing headline event if titles are close
            merged = False
            tkey = title.lower()[:80]
            for ev in events:
                if tkey and tkey in ev.title.lower():
                    # enrich
                    if a.get("evidence_id") and a["evidence_id"] not in ev.evidence_ids:
                        ev.evidence_ids.append(a["evidence_id"])
                    ev.snippet = (ev.snippet or body[:400])[:400]
                    # bump importance / polarity if the full article reveals more
                    _, new_imp = _score_polarity(text_for_match, category)
                    ev.importance = max(ev.importance, new_imp)
                    if polarity != "neutral":
                        ev.polarity = polarity  # type: ignore[assignment]
                    ev.ticker_match = max(ev.ticker_match, ticker_match)
                    merged = True
                    break

            if not merged:
                events.append(DevelopmentEvent(
                    evidence_ids=[a.get("evidence_id")] if a.get("evidence_id") else [],
                    category=category,
                    polarity=polarity,  # type: ignore[arg-type]
                    importance=importance,
                    title=title[:240] or "Article",
                    snippet=body[:400],
                    source=a.get("source_domain") or "",
                    published=a.get("date") or "",
                    ticker_match=ticker_match,
                    age_days=_compute_age_days(a.get("date")),
                ))

    return events
