"""Annual-report analyzer — turns extracted PDF text into a beginner-friendly guided tour.

For each standard section we know how to detect (Chairman's letter, MD&A,
risk factors, auditor's report, etc.) we return:
  - the section title
  - what it is (plain-English)
  - why pros read it
  - what to look for (red flags + green flags)
  - a short preview from the actual report (so the lesson is grounded)

We also extract a "Top numbers" panel with heuristic regex over the text:
revenue / profit / EPS / dividend / segment counts. These will not always
hit — we surface gracefully when they don't.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Section catalogue

SECTIONS: list[dict[str, Any]] = [
    {
        "key": "chairman_letter",
        "title": "Chairman's Letter / Letter to Shareholders",
        "icon": "✍️",
        "patterns": [
            r"chairman['’]?s\s+(letter|message|statement|address)",
            r"letter\s+(to\s+the\s+)?shareholders",
            r"message\s+from\s+the\s+chairman",
            r"managing\s+director['’]?s\s+(message|letter)",
        ],
        "what_it_is": (
            "An opening letter where the chairman (or MD) addresses shareholders about "
            "the year that was, the challenges, and the road ahead. Usually 2-6 pages."
        ),
        "why_pros_read_it": (
            "It's the highest-level narrative. Pros compare THIS year's tone against LAST "
            "year's — is the chairman more optimistic, more defensive, or hedging? Vague "
            "wording where specifics are expected is a yellow flag."
        ),
        "green_flags": [
            "Specific numbers and claims (market-share gain, capacity added, segment growth).",
            "Honest mention of misses or set-backs from the prior year.",
            "Consistent strategic priorities year-over-year (not pivoting every annual report).",
        ],
        "red_flags": [
            "Pure optimism with zero concrete metrics — 'transformative year', 'unlocking value' without numbers.",
            "No mention of risks at all in a year where the news flow had obvious risks.",
            "Strategic priorities completely different from last year — execution problems often hide in pivots.",
        ],
    },
    {
        "key": "mdna",
        "title": "Management Discussion and Analysis (MD&A)",
        "icon": "📊",
        "patterns": [
            r"management\s+discussion\s+(and|&)\s+analysis",
            r"\bmd[\s&\-]?a\b",
            r"management['’]?s\s+discussion",
            r"\boperations?\s+review\b",
        ],
        "what_it_is": (
            "The longest narrative section. Management explains the business, industry "
            "context, segment-by-segment performance, and the outlook. Required by SEBI."
        ),
        "why_pros_read_it": (
            "MD&A is where pros look for SEGMENT-level numbers (each business line's "
            "revenue and margin), capex plans, capacity utilisation, and forward-looking "
            "language. This is where you learn HOW the company actually makes money."
        ),
        "green_flags": [
            "Each segment has its own revenue, margin, and 'what changed' explanation.",
            "Clear capex plans tied to specific projects with timelines.",
            "Industry headwinds named explicitly, with the company's mitigation plan.",
        ],
        "red_flags": [
            "Only consolidated numbers — no segment break-down — when segments clearly matter.",
            "Generic boiler-plate language (every annual report from every company sounds the same here).",
            "Capacity utilisation falling but management calling it a 'one-off'.",
        ],
    },
    {
        "key": "financial_highlights",
        "title": "Financial Highlights / Key Numbers",
        "icon": "💰",
        "patterns": [
            r"financial\s+highlights",
            r"financial\s+summary",
            r"key\s+(financial\s+)?indicators",
            r"performance\s+at\s+a\s+glance",
            r"five[-\s]year\s+(summary|highlights|financial)",
            r"ten[-\s]year\s+(summary|highlights|financial)",
        ],
        "what_it_is": (
            "A compact table of revenue, profit, EPS, dividend, debt and key ratios — "
            "usually shown over 3, 5, or 10 years."
        ),
        "why_pros_read_it": (
            "This is where you check CONSISTENCY. One great year is luck; five great years "
            "is a pattern. Pros eyeball trend lines for revenue, margin, ROE, and debt."
        ),
        "green_flags": [
            "Revenue and profit both rising over 3-5 years.",
            "Operating margin stable or improving — not artificially boosted by 'other income'.",
            "Debt either flat or falling as revenue grows.",
        ],
        "red_flags": [
            "Revenue growing while profit flat or falling — costs running away.",
            "ROE / ROCE trending down for 2-3 years in a row.",
            "Debt growing FASTER than revenue.",
        ],
    },
    {
        "key": "risk_factors",
        "title": "Risk Factors / Risk Management",
        "icon": "⚠️",
        "patterns": [
            r"risk\s+factors",
            r"risks?\s+and\s+(concerns|mitigation|uncertainty)",
            r"principal\s+risks",
            r"risk\s+management",
        ],
        "what_it_is": (
            "A list of risks the business faces — regulatory, commodity, currency, "
            "competitive, technological, climate, etc. Required disclosure."
        ),
        "why_pros_read_it": (
            "Most retail investors skip this. Pros read it carefully because what's NOT "
            "listed is as telling as what is. Compare with last year — was a new risk added? "
            "Was an old one quietly removed?"
        ),
        "green_flags": [
            "Each risk is named SPECIFICALLY, with the mitigation step the company is taking.",
            "Risks are quantified where possible (e.g. '70% of revenue is from clients outside India').",
        ],
        "red_flags": [
            "Generic risks copy-pasted from a template ('competition', 'regulation', 'macro').",
            "No mitigation actions listed — just a wall of risk names.",
            "A risk that featured for 5 years suddenly removed without explanation.",
        ],
    },
    {
        "key": "auditor",
        "title": "Auditor's Report (Independent Auditor)",
        "icon": "🧾",
        "patterns": [
            r"independent\s+auditor['’]?s?\s+report",
            r"auditor['’]?s\s+(report|opinion)",
            r"report\s+on\s+the\s+(audit|financial\s+statements)",
        ],
        "what_it_is": (
            "An independent firm (Deloitte, EY, PwC, KPMG, Walker Chandiok, etc.) "
            "certifies whether the financial statements give a 'true and fair view'."
        ),
        "why_pros_read_it": (
            "You're looking for ONE specific thing: is the opinion UNMODIFIED (clean), "
            "or are there qualifications, emphasis-of-matter paragraphs, or adverse "
            "opinions? Any qualification is a major signal."
        ),
        "green_flags": [
            "An UNMODIFIED / UNQUALIFIED opinion (the standard clean version).",
            "Same audit firm for many years (continuity) — but watch for rotation rules.",
        ],
        "red_flags": [
            "Words like 'qualified opinion', 'adverse', 'disclaimer of opinion'.",
            "An 'emphasis of matter' paragraph drawing attention to anything unusual.",
            "A 'Key Audit Matter' that looks like the auditor is worried about an estimate.",
            "Auditor resigned mid-year and was replaced.",
        ],
    },
    {
        "key": "related_party",
        "title": "Related Party Transactions",
        "icon": "🤝",
        "patterns": [
            r"related\s+party\s+transactions?",
            r"related\s+party\s+disclosures",
            r"transactions?\s+with\s+related\s+parties",
        ],
        "what_it_is": (
            "Transactions between the company and entities controlled by promoters, "
            "directors, or their relatives — loans, sales, services, leases."
        ),
        "why_pros_read_it": (
            "Related-party transactions are LEGAL but a common channel for value to leak "
            "out of a listed company. Pros check the size relative to revenue, and whether "
            "the same party shows up year after year."
        ),
        "green_flags": [
            "Small absolute numbers relative to total revenue/expense.",
            "Each transaction has a clear business purpose noted.",
            "Independent directors have signed off on the audit-committee review.",
        ],
        "red_flags": [
            "Large 'loans and advances' to promoter-controlled entities.",
            "Recurring sales/purchases at non-market prices.",
            "Sharp increase in related-party numbers vs prior year.",
        ],
    },
    {
        "key": "contingent_liabilities",
        "title": "Contingent Liabilities & Commitments",
        "icon": "🔮",
        "patterns": [
            r"contingent\s+liabilit",
            r"commitments\s+and\s+contingencies",
            r"litigation\s+and\s+disputed\s+(matters|claims)",
        ],
        "what_it_is": (
            "Liabilities that MAY arise if certain events occur — pending litigation, "
            "tax demands, guarantees given, claims disputed by the company."
        ),
        "why_pros_read_it": (
            "These don't show on the balance-sheet headlines but can hit profit suddenly. "
            "Pros track the trend — are disputed tax demands going up or being resolved?"
        ),
        "green_flags": [
            "Each contingent item is named with the amount.",
            "Total contingent liabilities are small vs net worth.",
        ],
        "red_flags": [
            "Big tax / regulatory demands disputed for many years (case files just live there).",
            "Total contingent liabilities a large fraction of net worth.",
            "Sharp year-over-year jump in disputed amounts.",
        ],
    },
    {
        "key": "corporate_governance",
        "title": "Corporate Governance Report",
        "icon": "🏛️",
        "patterns": [
            r"corporate\s+governance",
            r"governance\s+report",
            r"board\s+of\s+directors",
        ],
        "what_it_is": (
            "Details on the board's composition, committee structure, attendance, and "
            "directors' compensation. SEBI requires it for listed companies."
        ),
        "why_pros_read_it": (
            "Independent-director count, audit-committee make-up, and director attendance "
            "are early signs of governance quality. Boards full of family members + low "
            "attendance is a structural warning."
        ),
        "green_flags": [
            "Majority of independent directors on the audit committee.",
            "Diverse board (gender, background, sector experience).",
            "High attendance at board and committee meetings.",
        ],
        "red_flags": [
            "Several directors classified as 'independent' but with long-standing ties to the promoter family.",
            "Multiple board seats per director (busy directors don't dig in).",
            "Promoter family holding key executive positions AND board chair.",
        ],
    },
    {
        "key": "directors_responsibility",
        "title": "Directors' Responsibility Statement",
        "icon": "🖋️",
        "patterns": [
            r"directors?['’]?\s+responsibility\s+statement",
            r"responsibility\s+statement\s+of\s+the\s+directors",
        ],
        "what_it_is": (
            "A short formal statement where directors affirm they've maintained accurate "
            "records and followed accounting standards. Boilerplate, mostly."
        ),
        "why_pros_read_it": (
            "Largely standard wording. Pros mostly check it exists and is signed."
        ),
        "green_flags": ["Present and signed by the board chair / company secretary."],
        "red_flags": ["Missing, or signed by someone unexpected."],
    },
    {
        "key": "outlook",
        "title": "Outlook / Future Plans",
        "icon": "🔭",
        "patterns": [
            r"\boutlook\b",
            r"future\s+(plans|prospects|outlook)",
            r"forward[-\s]looking",
        ],
        "what_it_is": (
            "Management's view of the next 12-24 months — industry conditions, planned "
            "capex, new product launches, expected market changes."
        ),
        "why_pros_read_it": (
            "Pros bank-check the previous year's outlook against THIS year's actuals. "
            "A management team that's consistently optimistic but consistently misses is "
            "a different beast than one that under-promises and over-delivers."
        ),
        "green_flags": [
            "Specific, measurable forward statements ('we plan to add X tonnes capacity').",
            "Last year's outlook largely materialised — credibility intact.",
        ],
        "red_flags": [
            "Pure adjectives — 'robust', 'transformative', 'exciting' — no metrics.",
            "Repeat of last year's outlook because last year's didn't happen.",
        ],
    },
]


# ---------------------------------------------------------------------------
# Detection

def _normalise(text: str) -> str:
    """Lowercase + collapse whitespace for matching."""
    return re.sub(r"\s+", " ", text.lower())


def _find_first(text_norm: str, patterns: list[str]) -> int | None:
    """Return character offset of the FIRST pattern hit, or None."""
    best = None
    for pat in patterns:
        m = re.search(pat, text_norm, re.IGNORECASE)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def _slice_preview(raw: str, start_norm: int, max_chars: int = 1400) -> str:
    """Return a readable preview slice from raw text, starting near `start_norm`
    and trimmed to whole sentences where possible.
    """
    # The normalised offset doesn't map 1:1 to raw. We approximate by searching
    # for the first 25-40 chars of the matched header in the raw text.
    start = max(0, start_norm - 5)
    # Walk forward past the header line
    chunk = raw[start:start + max_chars + 200]
    # Trim leading whitespace + try to start at the actual heading line
    chunk = chunk.lstrip()
    if len(chunk) > max_chars:
        # Cut at last sentence boundary
        cut = chunk[:max_chars]
        last = max(cut.rfind(". "), cut.rfind("\n"))
        if last > max_chars * 0.6:
            chunk = cut[:last + 1]
        else:
            chunk = cut + "…"
    return chunk.strip()


# ---------------------------------------------------------------------------
# Top-numbers extractor (heuristic)

_NUMBER = r"([\d,]+\.?\d*)"
_CR = r"(?:crores?|cr\.?|lakhs?|million|billion|mn|bn)"

_NUMBER_PATTERNS: list[tuple[str, str, str]] = [
    # (label, regex, beginner explanation)
    ("Total revenue / income",
     rf"(?:total\s+(?:income|revenue)|revenue\s+from\s+operations)[^\d]{{0,30}}{_NUMBER}\s*(?:{_CR})?",
     "Top line — total money the company brought in this year."),
    ("Net profit",
     rf"(?:net\s+profit|profit\s+(?:after|for)\s+(?:tax|the\s+year))[^\d]{{0,40}}{_NUMBER}\s*(?:{_CR})?",
     "Bottom line — what's left after all costs, interest, and taxes."),
    ("Earnings per share (EPS)",
     rf"(?:earnings?\s+per\s+share|basic\s+eps|diluted\s+eps)[^\d]{{0,40}}{_NUMBER}",
     "Your slice of profit per share you own."),
    ("Dividend per share",
     rf"(?:dividend\s+per\s+share|dividend\s+declared)[^\d]{{0,30}}{_NUMBER}",
     "Cash returned to shareholders per share."),
    ("Total debt / borrowings",
     rf"(?:total\s+borrowings|long[\s\-]term\s+borrowings|total\s+debt)[^\d]{{0,40}}{_NUMBER}\s*(?:{_CR})?",
     "Total amount the company owes lenders."),
]


def _extract_top_numbers(text: str) -> list[dict[str, str]]:
    """Return a list of {label, value, meaning} for numbers we could find."""
    out: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for label, pat, meaning in _NUMBER_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m and label not in seen_labels:
            out.append({
                "label": label,
                "value": m.group(1).strip().rstrip(","),
                "meaning": meaning,
            })
            seen_labels.add(label)
    return out


# ---------------------------------------------------------------------------
# Public API

def analyze_annual_report(
    text: str,
    company_hint: str | None = None,
) -> dict[str, Any]:
    """Return a structured guided-tour of the report.

    Output shape:
      {
        "company_hint": "...",
        "summary": {
          "total_chars": int,
          "sections_found": int,
          "sections_total": int,
        },
        "top_numbers": [ {label, value, meaning} ],
        "sections_found": [
          {
            "key", "title", "icon",
            "what_it_is", "why_pros_read_it",
            "green_flags", "red_flags",
            "preview"   # excerpt from the report
          }
        ],
        "sections_missing": [ {key, title, icon, what_it_is, why_pros_read_it} ],
        "what_you_learned": "..."   # closing beginner takeaway
      }
    """
    if not text or not text.strip():
        return {
            "ok": False,
            "error": "No text could be extracted from the PDF (it may be a scanned-image PDF).",
        }

    text_norm = _normalise(text)
    found: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for sec in SECTIONS:
        pos = _find_first(text_norm, sec["patterns"])
        if pos is None:
            missing.append({
                "key": sec["key"],
                "title": sec["title"],
                "icon": sec["icon"],
                "what_it_is": sec["what_it_is"],
                "why_pros_read_it": sec["why_pros_read_it"],
            })
            continue
        preview = _slice_preview(text, pos)
        found.append({
            "key": sec["key"],
            "title": sec["title"],
            "icon": sec["icon"],
            "what_it_is": sec["what_it_is"],
            "why_pros_read_it": sec["why_pros_read_it"],
            "green_flags": sec["green_flags"],
            "red_flags": sec["red_flags"],
            "preview": preview,
            "found_at_offset": pos,
        })

    top_numbers = _extract_top_numbers(text)

    return {
        "ok": True,
        "company_hint": company_hint,
        "summary": {
            "total_chars": len(text),
            "sections_found": len(found),
            "sections_total": len(SECTIONS),
        },
        "top_numbers": top_numbers,
        "sections_found": found,
        "sections_missing": missing,
        "what_you_learned": (
            "An annual report is a story told in numbered chapters — the chairman's letter "
            "is the opening narrative, MD&A is the deep dive, and the auditor's report is "
            "the independent reality check. As a beginner, learn to read these in ORDER, "
            "and learn to compare THIS year against LAST year. A single annual report tells "
            "you a snapshot; two side-by-side tell you the trajectory."
        ),
    }
