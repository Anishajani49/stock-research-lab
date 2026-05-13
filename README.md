# stock-research-assistant 🇮🇳

A **local-first** research assistant for the **Indian stock market** — NSE, BSE equities, and **AMFI mutual funds** — that runs on your MacBook Air M1.

It combines:

- **Deterministic analytics** (technical indicators, trend, risk rules) computed locally
- **Evidence store** (SQLite + FTS5) with citations
- **Ollama** used **only** for explanation/synthesis — never for facts
- **Strict JSON schema** output and guardrails to prevent hallucinations

> This is a research assistant, **not a trading bot**. It will never give price targets, never say "buy now", and always uses uncertainty language.

---

## What's supported

| Instrument | Where data comes from | How to input |
|---|---|---|
| NSE equity | yfinance (`.NS` suffix) | `RELIANCE`, `TCS.NS`, `INFY` |
| BSE equity | yfinance (`.BO` suffix) | `RELIANCE.BO` or use `--exchange BSE` |
| Mutual Fund | [mfapi.in](https://api.mfapi.in) (AMFI NAV) | scheme name (e.g. `axis bluechip`) or scheme code (e.g. `120586`) |

News outlets searched (ticker-specific via Google News India + direct RSS):

| Outlet | Domain |
|---|---|
| Economic Times | economictimes.indiatimes.com |
| Business Today | businesstoday.in |
| MoneyControl | moneycontrol.com |
| LiveMint | livemint.com |
| Business Standard | business-standard.com |
| Hindu BusinessLine | thehindubusinessline.com |
| Financial Express | financialexpress.com |
| CNBC TV18 | cnbctv18.com |
| NDTV Profit | ndtvprofit.com |
| Zee Business | zeebiz.com |

For **every** ticker the app runs one Google News India RSS query per outlet
(`site:<domain>`) in parallel, plus broad market-wide feeds as context fallback.
The final report shows a **per-source coverage** breakdown so you can see
exactly which outlets contributed.

You can **customize** the list via env var:

```bash
# .env — override the default source list (format: "Display Name|domain,...")
INDIA_NEWS_SOURCES=Economic Times|economictimes.indiatimes.com,Mint|livemint.com
NEWS_PER_SOURCE_MAX=3
```

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- A small model pulled, e.g.:
  ```
  ollama pull llama3.2:3b
  ```

Optional (for chart OCR):
```
brew install tesseract
```

---

## Install

```bash
cd stock-research-assistant
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

---

## Usage — CLI

```bash
# Equity (auto-tries NSE then BSE)
python -m app.main --ticker RELIANCE
python -m app.main --ticker TCS.NS --timeframe 1y
python -m app.main --ticker ASIANPAINT --exchange BSE

# Mutual Fund — by scheme code
python -m app.main --mf --ticker 120586
python -m app.main --mf --ticker 120586 --timeframe 3y

# Mutual Fund — by name (auto-resolves top match)
python -m app.main --mf --ticker "axis bluechip"

# Skip LLM (deterministic only)
python -m app.main --ticker RELIANCE --no-llm
```

Output:
- A Markdown report printed to the terminal
- Saved to `data/processed/<TICKER>_<timestamp>.md`
- Evidence persisted in `data/cache/evidence.sqlite`

## Usage — Streamlit UI

```bash
make ui
# or
streamlit run app/ui/streamlit_app.py
```

- Pick **Equity (NSE/BSE)** → type `RELIANCE` / `TCS.NS` / `INFY`
- Pick **Mutual Fund** → type a name (e.g. `parag parikh flexi`) → select from AMFI search results, or type a scheme code directly

## Makefile

```
make run TICKER=RELIANCE        # run CLI for equity
make ui                         # open Streamlit dashboard
make test                       # run unit tests
```

---

## Project Layout

```
stock-research-assistant/
  app/
    main.py                       # Typer CLI entrypoint
    config.py                     # India defaults (INR, NSE, AMFI)
    orchestrator.py               # Routes equity vs MF; parallel fetches
    schemas/                      # Pydantic models
    adapters/
      market_yfinance.py          # NSE/BSE via yfinance
      mfapi.py                    # AMFI mutual funds via mfapi.in
      news_rss.py                 # Indian financial news feeds
      blog_extractor.py
      youtube_transcript.py
      chart_image.py
    analysis/                     # Deterministic analytics
    llm/                          # Ollama client + guardrails
    storage/                      # SQLite + FTS5 evidence store
    reports/render_markdown.py    # INR formatting, MF variant
    ui/
      cli.py                      # Rich terminal output
      streamlit_app.py            # Local dashboard with MF search
  tests/
  data/
```

---

## Safety & Product Rules

- No cloud LLMs; only local Ollama
- No trading execution
- No guaranteed advice, no price targets
- All conclusions must cite evidence IDs
- Missing data is explicitly reported
- Uncertainty phrasing enforced by guardrails

---

## Disclaimer

This tool is for **educational and research purposes only**. It is **not** financial advice. Markets are subject to risk; past performance does not guarantee future results. Always consult a **SEBI-registered financial advisor** before making investment decisions.
