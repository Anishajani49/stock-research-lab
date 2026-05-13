"""Rich CLI rendering helpers."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from app.schemas.output import ResearchState

console = Console()


def print_header(state: ResearchState) -> None:
    meta = state.company_meta or {}
    title = f"[bold]{state.ticker}[/bold] — {meta.get('long_name', state.ticker)}"
    sub = f"timeframe={state.timeframe}  sector={meta.get('sector') or 'n/a'}"
    console.print(Panel.fit(f"{title}\n{sub}", border_style="cyan"))


def print_summary_table(state: ResearchState) -> None:
    snap = state.indicators
    t = Table(title="Key Numbers", show_header=True, header_style="bold magenta")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    t.add_row("Last Close", f"{snap.last_close}")
    t.add_row("SMA20 / 50 / 200", f"{snap.sma20} / {snap.sma50} / {snap.sma200}")
    t.add_row("RSI14", f"{snap.rsi14}")
    t.add_row("MACD hist", f"{snap.macd_hist}")
    t.add_row("ATR14", f"{snap.atr14}")
    t.add_row("Trend", state.trend)
    t.add_row("Sentiment", f"{state.sentiment.label} ({state.sentiment.score:+.2f})")
    t.add_row("Stance", f"{state.stance.label}  (score {state.stance.score:+.2f})")
    t.add_row("Confidence", f"{state.confidence} ({state.confidence_score:.2f})")
    console.print(t)


def print_markdown(md: str) -> None:
    console.print(Markdown(md))


def print_missing(state: ResearchState) -> None:
    if state.missing:
        console.print(Panel.fit(
            "\n".join(f"• {m}" for m in state.missing),
            title="⚠️  Missing data", border_style="yellow",
        ))
