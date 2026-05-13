"""FastAPI server — the only entry point for the new web UI.

Endpoints:
  GET /api/search?q=...                 — basic ticker autocomplete (yfinance)
  GET /api/analyze?ticker=...&...       — full deterministic analysis (no LLM by default)
  GET /api/learn?ticker=...&...         — candlestick learning lesson + OHLCV
  GET /api/glossary                     — beginner finance dictionary

Static frontend served at /  (web/ folder).

Run:
  uvicorn app.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters import annual_report as annual_report_adapter
from app.analysis.health_score import build_health_scorecard
from app.analysis.stance_explainer import build_stance_explanation
from app.learn.analyst_thinking import build_analyst_workflow
from app.learn.annual_report_analyzer import analyze_annual_report
from app.learn.glossary import get_glossary
from app.orchestrator import run as orch_run, run_learn
from app.schemas.input import ResearchRequest

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"

app = FastAPI(
    title="Stock Research Assistant — Educational",
    description="Beginner-friendly stock learning + analysis. Educational only — not investment advice.",
    version="0.2.0",
)

# Wide-open CORS — local dev only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ticker search

_POPULAR_INDIAN_TICKERS: list[dict[str, str]] = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd",        "exchange": "NSE"},
    {"symbol": "TCS",      "name": "Tata Consultancy Services Ltd",  "exchange": "NSE"},
    {"symbol": "INFY",     "name": "Infosys Ltd",                    "exchange": "NSE"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd",                  "exchange": "NSE"},
    {"symbol": "ICICIBANK","name": "ICICI Bank Ltd",                 "exchange": "NSE"},
    {"symbol": "ITC",      "name": "ITC Ltd",                        "exchange": "NSE"},
    {"symbol": "SBIN",     "name": "State Bank of India",            "exchange": "NSE"},
    {"symbol": "BHARTIARTL","name": "Bharti Airtel Ltd",             "exchange": "NSE"},
    {"symbol": "LT",       "name": "Larsen & Toubro Ltd",            "exchange": "NSE"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd",                  "exchange": "NSE"},
    {"symbol": "KOTAKBANK","name": "Kotak Mahindra Bank Ltd",        "exchange": "NSE"},
    {"symbol": "WIPRO",    "name": "Wipro Ltd",                      "exchange": "NSE"},
    {"symbol": "HCLTECH",  "name": "HCL Technologies Ltd",           "exchange": "NSE"},
    {"symbol": "MARUTI",   "name": "Maruti Suzuki India Ltd",        "exchange": "NSE"},
    {"symbol": "TATAMOTORS","name": "Tata Motors Ltd",               "exchange": "NSE"},
    {"symbol": "TATASTEEL","name": "Tata Steel Ltd",                 "exchange": "NSE"},
    {"symbol": "ASIANPAINT","name": "Asian Paints Ltd",              "exchange": "NSE"},
    {"symbol": "BAJFINANCE","name": "Bajaj Finance Ltd",             "exchange": "NSE"},
    {"symbol": "TITAN",    "name": "Titan Company Ltd",              "exchange": "NSE"},
    {"symbol": "HINDUNILVR","name": "Hindustan Unilever Ltd",        "exchange": "NSE"},
    {"symbol": "ULTRACEMCO","name": "UltraTech Cement Ltd",          "exchange": "NSE"},
    {"symbol": "SUNPHARMA","name": "Sun Pharmaceutical Industries",  "exchange": "NSE"},
    {"symbol": "DRREDDY",  "name": "Dr. Reddy's Laboratories",       "exchange": "NSE"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd",          "exchange": "NSE"},
    {"symbol": "ADANIPORTS","name": "Adani Ports & SEZ Ltd",         "exchange": "NSE"},
    {"symbol": "POWERGRID","name": "Power Grid Corporation",         "exchange": "NSE"},
    {"symbol": "NTPC",     "name": "NTPC Ltd",                       "exchange": "NSE"},
    {"symbol": "ONGC",     "name": "Oil and Natural Gas Corp",       "exchange": "NSE"},
    {"symbol": "COALINDIA","name": "Coal India Ltd",                 "exchange": "NSE"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd",                  "exchange": "NSE"},
    {"symbol": "NESTLEIND","name": "Nestle India Ltd",               "exchange": "NSE"},
    {"symbol": "BAJAJFINSV","name": "Bajaj Finserv Ltd",             "exchange": "NSE"},
    {"symbol": "M&M",      "name": "Mahindra & Mahindra Ltd",        "exchange": "NSE"},
    {"symbol": "TECHM",    "name": "Tech Mahindra Ltd",              "exchange": "NSE"},
    {"symbol": "BRITANNIA","name": "Britannia Industries Ltd",       "exchange": "NSE"},
    {"symbol": "DIVISLAB", "name": "Divi's Laboratories",            "exchange": "NSE"},
    {"symbol": "CIPLA",    "name": "Cipla Ltd",                      "exchange": "NSE"},
    {"symbol": "GRASIM",   "name": "Grasim Industries Ltd",          "exchange": "NSE"},
    {"symbol": "BPCL",     "name": "Bharat Petroleum Corp",          "exchange": "NSE"},
    {"symbol": "IOC",      "name": "Indian Oil Corporation",         "exchange": "NSE"},
    {"symbol": "ZOMATO",   "name": "Zomato Ltd",                     "exchange": "NSE"},
    {"symbol": "PAYTM",    "name": "One 97 Communications (Paytm)",  "exchange": "NSE"},
    {"symbol": "NYKAA",    "name": "FSN E-Commerce (Nykaa)",         "exchange": "NSE"},
    {"symbol": "DMART",    "name": "Avenue Supermarts (DMart)",      "exchange": "NSE"},
    {"symbol": "IRCTC",    "name": "Indian Railway Catering",        "exchange": "NSE"},
    {"symbol": "TATAPOWER","name": "Tata Power Company Ltd",         "exchange": "NSE"},
    {"symbol": "VEDL",     "name": "Vedanta Ltd",                    "exchange": "NSE"},
]


@app.get("/api/search")
def search(q: str = Query(default="", description="Ticker symbol or company name")) -> dict[str, Any]:
    """Lightweight client-side autocomplete from a curated NSE list."""
    q = (q or "").strip().upper()
    if not q:
        return {"results": _POPULAR_INDIAN_TICKERS[:15]}
    matches: list[dict[str, str]] = []
    for it in _POPULAR_INDIAN_TICKERS:
        if q in it["symbol"].upper() or q in it["name"].upper():
            matches.append(it)
    # Always allow searching by raw symbol even if not in our curated list
    if not matches and q.isalnum():
        matches.append({"symbol": q, "name": q, "exchange": "NSE"})
    return {"results": matches[:25]}


# ---------------------------------------------------------------------------
# Analyze

@app.get("/api/analyze")
def analyze(
    ticker: str = Query(..., min_length=1),
    timeframe: str = Query("6mo"),
    exchange: str = Query("auto"),
    skip_llm: bool = Query(True, description="Skip LLM synthesis (faster, deterministic only)"),
) -> JSONResponse:
    """Run the full analysis pipeline and return JSON suitable for the dashboard."""
    try:
        request = ResearchRequest(
            ticker=ticker.upper().strip(),
            mode="analyze",
            instrument_type="equity",
            exchange=exchange,
            timeframe=timeframe,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid input: {e}")

    if skip_llm:
        # Replace synthesize with the deterministic fallback
        from app.llm import synthesis as _s
        original = _s.synthesize

        def _skip(state, client=None):  # noqa: ARG001
            return _s._fallback_explanation(state, reason="skip-llm flag")
        _s.synthesize = _skip  # type: ignore[assignment]
        try:
            state = orch_run(request)
        finally:
            _s.synthesize = original  # type: ignore[assignment]
    else:
        state = orch_run(request)

    payload = state.model_dump(mode="json")
    # Add the educational layers built specifically for the new UI
    payload["health_scorecard"] = build_health_scorecard(state)
    payload["analyst_workflow"] = build_analyst_workflow(state)
    payload["stance_explanation"] = build_stance_explanation(state)
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Learn (candlestick lesson)

@app.get("/api/learn")
def learn(
    ticker: str = Query("", description="Optional — if provided, real-chart detections are attached"),
    timeframe: str = Query("6mo"),
    exchange: str = Query("auto"),
) -> JSONResponse:
    try:
        request = ResearchRequest(
            ticker=(ticker or "RELIANCE").upper().strip(),
            mode="learn",
            instrument_type="equity",
            exchange=exchange,
            timeframe=timeframe,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid input: {e}")

    lesson = run_learn(request)
    return JSONResponse(lesson.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Glossary

@app.get("/api/glossary")
def glossary() -> dict[str, Any]:
    return {"glossary": get_glossary()}


# ---------------------------------------------------------------------------
# Annual report analyzer

@app.post("/api/annual_report")
async def annual_report(
    url: str = Form(default=""),
    company_hint: str = Form(default=""),
    file: UploadFile | None = File(default=None),
) -> JSONResponse:
    """Analyze a public annual-report PDF. Accept EITHER a URL or an uploaded file."""
    pdf_bytes: bytes | None = None
    src_label = ""

    if file is not None and file.filename:
        try:
            pdf_bytes = await file.read()
            src_label = file.filename
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"could not read upload: {e}")
    elif url:
        fetched = annual_report_adapter.fetch_pdf_from_url(url.strip())
        if not fetched["ok"]:
            raise HTTPException(status_code=400, detail=fetched["error"] or "could not fetch URL")
        pdf_bytes = fetched["bytes"]
        src_label = url
    else:
        raise HTTPException(status_code=400, detail="Provide either a PDF URL or upload a PDF file.")

    extracted = annual_report_adapter.extract_text(pdf_bytes)
    if not extracted["ok"]:
        raise HTTPException(status_code=422, detail=extracted["error"] or "could not extract text from PDF")

    analysis = analyze_annual_report(extracted["text"], company_hint=company_hint or None)
    payload = {
        "source": src_label,
        "pdf_meta": {
            "n_pages":      extracted["n_pages"],
            "n_pages_read": extracted["n_pages_read"],
        },
        "analysis": analysis,
    }
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Static frontend

if WEB_DIR.exists():
    # Mount sub-folders for assets so direct paths like /css/styles.css work
    if (WEB_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    if (WEB_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

    @app.get("/")
    def root_index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/dashboard")
    def page_dashboard() -> FileResponse:
        return FileResponse(WEB_DIR / "dashboard.html")

    @app.get("/learn")
    def page_learn() -> FileResponse:
        return FileResponse(WEB_DIR / "learn.html")

    @app.get("/glossary")
    def page_glossary() -> FileResponse:
        return FileResponse(WEB_DIR / "glossary.html")

    @app.get("/annual-report")
    def page_annual_report() -> FileResponse:
        return FileResponse(WEB_DIR / "annual-report.html")
