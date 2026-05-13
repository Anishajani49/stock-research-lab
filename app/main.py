"""CLI entrypoint — two modes: `analyze` (default) and `learn`."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from app.config import settings
from app.orchestrator import run as orch_run, run_learn
from app.reports.render_learning import render_lesson, save_lesson
from app.reports.render_markdown import render, save_report
from app.schemas.input import ResearchRequest
from app.ui.cli import (
    console,
    print_header,
    print_markdown,
    print_missing,
    print_summary_table,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def analyze(
    ticker: str = typer.Option(
        ...,
        "--ticker", "-t",
        help="NSE/BSE symbol (e.g. 'RELIANCE', 'TCS.NS', 'INFY.BO') or MF scheme code/name",
    ),
    mode: str = typer.Option(
        "analyze",
        "--mode", "-m",
        help="'analyze' (full stock research) or 'learn' (candlestick lesson).",
    ),
    instrument: str = typer.Option(
        "equity",
        "--instrument", "-i",
        help="'equity' or 'mutual_fund' (shortcut: --mf).",
    ),
    mf: bool = typer.Option(False, "--mf", help="Shortcut for --instrument mutual_fund"),
    exchange: str = typer.Option(
        "auto", "--exchange", "-e",
        help="'NSE', 'BSE', or 'auto'. Equity only.",
    ),
    scheme_code: Optional[str] = typer.Option(
        None, "--scheme-code", help="AMFI scheme code if known (mutual funds).",
    ),
    timeframe: str = typer.Option(
        settings.DEFAULT_TIMEFRAME, "--timeframe",
        help="1mo | 3mo | 6mo | 1y | 2y | 5y | ytd | max",
    ),
    chart: Optional[Path] = typer.Option(None, "--chart", help="Optional chart image path"),
    youtube: list[str] = typer.Option([], "--youtube", "-y", help="YouTube URL(s)"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM synthesis (deterministic only)"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save markdown to data/processed/"),
) -> None:
    """Indian stock + MF research assistant — analyze mode or candlestick learn mode."""
    resolved_mode = mode.strip().lower()
    resolved_instrument = "mutual_fund" if mf else instrument.strip().lower()

    request = ResearchRequest(
        ticker=ticker,
        mode=resolved_mode,  # type: ignore[arg-type]
        instrument_type=resolved_instrument,  # type: ignore[arg-type]
        exchange=exchange,  # type: ignore[arg-type]
        timeframe=timeframe,
        mf_scheme_code=scheme_code,
        chart_image=chart,
        youtube_urls=list(youtube),
    )

    # ---- Learning mode ---------------------------------------------------
    if request.is_learn_mode:
        with console.status(f"[cyan]Building candlestick lesson for {request.ticker}...[/cyan]"):
            lesson = run_learn(request)
        md = render_lesson(lesson)
        print_markdown(md)
        if save:
            path = save_lesson(lesson, md)
            console.print(f"\n[green]Lesson saved to:[/green] {path}")
        return

    # ---- Analysis mode ---------------------------------------------------
    if no_llm:
        from app.llm import synthesis as _s

        def _skip(state, client=None):  # noqa: ARG001
            return _s._fallback_explanation(state, reason="--no-llm flag")

        _s.synthesize = _skip  # type: ignore[assignment]

    label = "MF" if request.is_mutual_fund else request.exchange
    with console.status(f"[cyan]Analyzing {request.ticker} [{label}, {request.timeframe}]...[/cyan]"):
        state = orch_run(request)

    print_header(state)
    print_missing(state)
    print_summary_table(state)

    md = render(state)
    print_markdown(md)

    if save:
        path = save_report(state, md)
        console.print(f"\n[green]Report saved to:[/green] {path}")


if __name__ == "__main__":
    typer.run(analyze)
