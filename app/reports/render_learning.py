"""Markdown renderer for the Candlestick Learning Mode lesson."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.schemas.output import LearningLesson


BIAS_BADGE = {
    "bullish": "🟢 bullish",
    "bearish": "🔴 bearish",
    "neutral": "⚪ neutral",
}


def _render_anatomy(section: dict) -> str:
    notes = "\n".join(f"- {n}" for n in section.get("notes", []))
    return (
        f"## {section['title']}\n\n"
        f"{section['intro']}\n\n"
        f"```\n{section['diagram']}\n```\n\n"
        f"{notes}\n"
    )


def _render_bullish_vs_bearish(section: dict) -> str:
    lines = [f"## {section['title']}\n"]
    for item in section.get("items", []):
        lines.append(
            f"### {item['kind']}\n"
            f"- **What:** {item['what']}\n"
            f"- **Meaning:** {item['meaning']}\n"
        )
    if section.get("note"):
        lines.append(f"\n> {section['note']}\n")
    return "\n".join(lines)


def _render_pattern(section: dict) -> str:
    name = section["display"]
    bias = BIAS_BADGE.get(section.get("bias", "neutral"), section.get("bias", ""))
    ascii_ex = section.get("example_ascii", "")
    real = section.get("real_examples") or []

    real_md = ""
    if real:
        lines = []
        for r in real:
            conf = r.get("confidence", 0.0)
            date = r.get("date") or f"bar #{r.get('index')}"
            lines.append(f"- **{date}** · confidence {conf:.2f} · {r.get('note','')}")
        real_md = "\n**Real examples in your data:**\n" + "\n".join(lines) + "\n"
    else:
        real_md = "\n_No textbook-grade examples found in the current data window._\n"

    return (
        f"### {name}  ·  {bias}\n\n"
        f"**What it is:** {section['what_it_is']}\n\n"
        f"**What it may suggest:** {section['what_it_may_suggest']}\n\n"
        f"**When it matters:** {section['when_it_matters']}\n\n"
        f"**When it fails:** {section['when_it_fails']}\n\n"
        f"**Confirmation:** {section['confirmation']}\n\n"
        f"```\n{ascii_ex}\n```\n"
        f"{real_md}\n"
    )


def _render_context(section: dict) -> str:
    bullets = "\n".join(f"- {b}" for b in section.get("bullets", []))
    return f"## {section['title']}\n\n{bullets}\n"


def render_lesson(lesson: LearningLesson) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_bits = []
    if lesson.ticker:
        header_bits.append(f"**Ticker:** `{lesson.ticker}`")
    if lesson.company_name:
        header_bits.append(f"**Company:** {lesson.company_name}")
    if lesson.timeframe:
        header_bits.append(f"**Timeframe:** {lesson.timeframe}")
    if lesson.n_bars:
        header_bits.append(f"**Bars analysed:** {lesson.n_bars}")
    if lesson.last_close is not None:
        header_bits.append(f"**Last close:** ₹{lesson.last_close:,.2f}")
    header = "  |  ".join(header_bits) + f"  |  **Generated:** {generated_at}"

    parts: list[str] = [
        "# Candlestick Learning Mode\n",
        header + "\n",
        "_A beginner-friendly walk-through of candlestick charts. No trade signals — "
        "just what each pattern is, when it matters, and when it fails._\n",
        "---\n",
    ]

    # Split sections: anatomy, bullish_vs_bearish, singles, multis, context
    single_patterns = []
    multi_patterns = []
    context_section = None
    anatomy_section = None
    bvb_section = None

    for sec in lesson.lesson_sections:
        t = sec.get("type")
        if t == "anatomy":
            anatomy_section = sec
        elif t == "bullish_vs_bearish":
            bvb_section = sec
        elif t == "pattern":
            if sec.get("pattern_type") == "single":
                single_patterns.append(sec)
            else:
                multi_patterns.append(sec)
        elif t == "context":
            context_section = sec

    if anatomy_section:
        parts.append(_render_anatomy(anatomy_section))
        parts.append("---\n")
    if bvb_section:
        parts.append(_render_bullish_vs_bearish(bvb_section))
        parts.append("---\n")

    if single_patterns:
        parts.append("## Single-candle patterns\n")
        for p in single_patterns:
            parts.append(_render_pattern(p))
        parts.append("---\n")

    if multi_patterns:
        parts.append("## Multi-candle patterns\n")
        for p in multi_patterns:
            parts.append(_render_pattern(p))
        parts.append("---\n")

    if context_section:
        parts.append(_render_context(context_section))
        parts.append("---\n")

    # Recent detections summary
    if lesson.detections:
        parts.append("## 📍 Recent detections on your data (newest first)\n")
        rows = []
        for d in lesson.detections[:15]:
            rows.append(
                f"| {d.date or '-'} | `{d.pattern}` | {BIAS_BADGE.get(d.bias, d.bias)} "
                f"| {d.confidence:.2f} | {d.note} |"
            )
        parts.append(
            "| Date | Pattern | Bias | Confidence | Note |\n"
            "|---|---|---|---|---|\n"
            + "\n".join(rows) + "\n"
        )
        parts.append("---\n")

    parts.append(
        "## ⚖️ Disclaimer\n\n"
        "This is educational material, not financial advice. Detected patterns are "
        "heuristic approximations — real trading decisions require wider context, "
        "fundamentals, and position sizing.\n"
    )

    return "\n".join(parts)


def save_lesson(lesson: LearningLesson, md: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = (lesson.ticker or "lesson").replace("/", "_")
    out = settings.PROCESSED_DIR / f"learn_{safe}_{ts}.md"
    out.write_text(md, encoding="utf-8")
    return out
