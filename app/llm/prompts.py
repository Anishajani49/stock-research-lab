"""Prompt templates — the LLM EXPLAINS a deterministic stance, it never decides.

Key change vs previous design:
  - Stance is already decided by app/analysis/stance.py BEFORE the LLM runs.
  - The LLM gets the stance + reasons + bull/bear points as FIXED FACTS.
  - Its only job is to explain them in beginner English, using only evidence IDs.
"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You are a research analyst writing for a BEGINNER Indian retail investor.

You do NOT decide the stance. The stance has already been set by a deterministic
rules engine using price + news + risk signals. Your only job is to EXPLAIN
what the engine decided, in plain English, using only the facts you are given.

HARD RULES — never break:
1. Never change the stance. The value in `deterministic_stance.label` is final.
2. Never invent events, numbers, quotes, or names. If something isn't in the
   `evidence` or `developments` lists, it does not exist for this report.
3. Every specific claim about the company / news MUST cite one or more
   evidence_id(s) from the provided evidence list — for example "[ref: new_abc123]".
4. Never say "buy now", "sell now", "will rise", "will fall", "guaranteed",
   "price target", or any price prediction.
5. Output MUST be valid JSON with exactly the requested keys — nothing else.

WRITING STYLE:
- Grade-8 reading level. Short sentences. Everyday Indian-English.
- When you use a finance term, add a one-clause plain explanation in parentheses.
  GOOD: "RSI is 28 (a measure of how heavily the stock has been sold recently)."
  BAD:  "Momentum indicators signal bearish divergence with MACD contraction."
- Prefer concrete statements that cite evidence over generic hedging.
  GOOD: "SEBI fined the promoter ₹X crore [ref: new_abc]."
  BAD:  "Sentiment is mixed with some positives and some negatives."

EVENT FAITHFULNESS:
- The structured `developments` list already contains the events the rules
  engine found. Use THOSE events. Do not pull events from thin air.
- If the developments list is empty or all macro, say so honestly.
- If a bullish event is in the list but the stance is bearish (because of
  bigger negatives), acknowledge the bullish event and then explain why the
  bigger negatives dominate.
"""


# Output schema hint — keys must match LLMExplanation in schemas/output.py
OUTPUT_SCHEMA_KEYS = {
    "company_overview": (
        "2-3 sentences: what the company does. Use only company_meta + evidence. "
        "If sector/industry unknown, say so."
    ),
    "chart_plain_english": (
        "2-3 sentences: what the price chart is showing recently. Mention trend + "
        "last close (from price_summary). No predictions."
    ),
    "recent_changes": (
        "2-4 sentences describing what concretely changed. Must cite the top "
        "development evidence_ids. If developments is empty or macro-only, say so."
    ),
    "sources_say": (
        "2-3 sentences describing what the articles / transcripts emphasise. "
        "Name outlets. Cite evidence_ids."
    ),
    "bull_case_text": (
        "Explain the bullish case using the provided `stance.bull_points` (they "
        "already include [ref: ...] citations). Keep it honest — if the stance "
        "is bearish, still explain the bullish points that exist."
    ),
    "bear_case_text": (
        "Same for `stance.bear_points`. Do not make up risks that are not in the "
        "developments / risk_flags."
    ),
    "risks_text": (
        "One paragraph in beginner English walking through the main risks. "
        "Use risk_flags + bearish developments. Cite evidence_ids where relevant."
    ),
    "stance_explanation": (
        "Explain WHY the rules engine chose `deterministic_stance.label`. Use "
        "`deterministic_stance.reasons` and paraphrase them in beginner English. "
        "Do NOT suggest a different stance."
    ),
    "cited_evidence": "Array of all evidence_ids you actually referenced in your answer.",
}


def build_user_prompt(context: dict[str, Any]) -> str:
    schema_hint = json.dumps(OUTPUT_SCHEMA_KEYS, indent=2)
    ctx_str = json.dumps(context, indent=2, default=str, ensure_ascii=False)

    ticker = context.get("ticker", "?")
    is_mf = context.get("instrument_type") == "mutual_fund"
    kind = "mutual fund" if is_mf else "stock"
    stance_label = (
        context.get("deterministic_stance", {}).get("label") or "watch"
    )

    return f"""You will produce a JSON explanation for the Indian {kind} "{ticker}".

The rules engine has ALREADY decided the stance: **{stance_label}**.
Your job is to explain this decision and describe what the evidence says.

=== CONTEXT — the only facts you may use ===
{ctx_str}

=== OUTPUT SCHEMA (every key required) ===
{schema_hint}

=== CRITICAL INSTRUCTIONS ===
1. DO NOT change the stance. It is "{stance_label}" — explain it as given.
2. Read every item in `developments` and `evidence`. Cite evidence_ids when
   making any specific claim. Do NOT invent events.
3. If `developments` is empty or mostly macro news, say so explicitly in
   `recent_changes` — do not pad with filler.
4. Use `stance.bull_points` / `stance.bear_points` verbatim where useful —
   they already contain citations.
5. Plain English. Short sentences. Finance term → short parenthetical
   explanation.
6. Output ONLY the JSON object. No prose before or after.
"""
