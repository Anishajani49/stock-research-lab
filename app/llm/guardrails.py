"""Guardrails for the LLM explanation output.

Since the stance is now deterministic (not picked by the LLM), these rails are
simpler: strip trade-signal language, filter citations to the whitelist, and
force the return shape into LLMExplanation.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.output import LLMExplanation


UNCERTAINTY_REPLACEMENTS = [
    (re.compile(r"\bguaranteed\b", re.I), "uncertain"),
    (re.compile(r"\bwill\s+(rise|fall|reach|hit|double|triple|go\s+up|go\s+down)\b", re.I), r"may \1"),
    (re.compile(r"\bdefinitely\s+(rise|fall|go\s+up|go\s+down)\b", re.I), r"may \1"),
    (re.compile(r"\bprice\s+target\b", re.I), "price level worth watching"),
    (re.compile(r"\btarget\s+price\b", re.I), "price level worth watching"),
    (re.compile(r"\bbuy\s+now\b", re.I), "see the stance section"),
    (re.compile(r"\bsell\s+now\b", re.I), "see the stance section"),
    (re.compile(r"\byou\s+should\s+buy\b", re.I), "the evidence-based stance is shown above"),
    (re.compile(r"\byou\s+should\s+sell\b", re.I), "the evidence-based stance is shown above"),
    (re.compile(r"\bfinancial\s+advice\b", re.I), "research note"),
    (re.compile(r"\binvestment\s+advice\b", re.I), "research note"),
]

FORBIDDEN_PATTERNS = [
    re.compile(r"\bguaranteed\b", re.I),
    re.compile(r"\bprice\s+target\b", re.I),
    re.compile(r"\btarget\s+price\b", re.I),
    re.compile(r"\bbuy\s+now\b", re.I),
    re.compile(r"\bsell\s+now\b", re.I),
]


def sanitize_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in UNCERTAINTY_REPLACEMENTS:
        out = pat.sub(repl, out)
    return out


def contains_forbidden(text: str) -> list[str]:
    if not text:
        return []
    hits = []
    for pat in FORBIDDEN_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def filter_citations(claimed: list[str], allowed: set[str]) -> list[str]:
    if not claimed:
        return []
    return [cid for cid in claimed if cid in allowed]


def _str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return str(v)


def _list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str):
        return [p.strip("-• ").strip() for p in re.split(r"[\n;]+", v) if p.strip()]
    return [str(v)]


def coerce_explanation(raw: dict[str, Any]) -> LLMExplanation:
    return LLMExplanation(
        company_overview=_str(raw.get("company_overview")),
        chart_plain_english=_str(raw.get("chart_plain_english")),
        recent_changes=_str(raw.get("recent_changes")),
        sources_say=_str(raw.get("sources_say")),
        bull_case_text=_str(raw.get("bull_case_text")),
        bear_case_text=_str(raw.get("bear_case_text")),
        risks_text=_str(raw.get("risks_text")),
        stance_explanation=_str(raw.get("stance_explanation")),
        cited_evidence=_list(raw.get("cited_evidence")),
    )


def apply_guardrails(explanation: LLMExplanation, allowed_evidence_ids: set[str]) -> LLMExplanation:
    data = explanation.model_dump()
    text_keys = (
        "company_overview", "chart_plain_english", "recent_changes", "sources_say",
        "bull_case_text", "bear_case_text", "risks_text", "stance_explanation",
    )
    for key in text_keys:
        data[key] = sanitize_text(data.get(key, ""))
    data["cited_evidence"] = filter_citations(data.get("cited_evidence", []), allowed_evidence_ids)
    return LLMExplanation(**data)
