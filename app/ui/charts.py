"""Plotly candlestick chart with pattern-detection annotations.

Used by the Streamlit Candlestick Learning tab. Pure presentation — all the
real work (OHLCV fetch + detection) happens upstream in the orchestrator /
detector. This module just paints.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from app.schemas.output import CandleDetection


# Color per bias so markers speak for themselves.
_BIAS_COLOR = {
    "bullish": "#22c55e",   # green
    "bearish": "#ef4444",   # red
    "neutral": "#64748b",   # slate
}

# Offset (fraction of price range) used to place markers above/below a bar
# so they don't sit on top of the candle.
_OFFSET_FRAC = 0.04


def _pretty_pattern(name: str) -> str:
    return name.replace("_", " ").title()


def build_candlestick_figure(
    ohlcv: list[dict[str, Any]],
    detections: list[CandleDetection],
    ticker: str | None = None,
    company_name: str | None = None,
    timeframe: str | None = None,
) -> go.Figure:
    """Return a Plotly Figure with the candlestick chart + pattern markers."""
    if not ohlcv:
        return go.Figure()

    dates = [str(b.get("Date") or "") for b in ohlcv]
    opens = [float(b.get("Open") or 0.0) for b in ohlcv]
    highs = [float(b.get("High") or 0.0) for b in ohlcv]
    lows = [float(b.get("Low") or 0.0) for b in ohlcv]
    closes = [float(b.get("Close") or 0.0) for b in ohlcv]

    # Main candlestick trace
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=dates,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name="Price",
                increasing_line_color="#16a34a",
                decreasing_line_color="#dc2626",
                showlegend=False,
            )
        ]
    )

    # Range for offset calculation
    if highs and lows:
        price_span = max(highs) - min(lows)
        offset = max(price_span * _OFFSET_FRAC, 0.1)
    else:
        offset = 1.0

    # Group detections by bias so legend is clean
    grouped: dict[str, list[CandleDetection]] = {"bullish": [], "bearish": [], "neutral": []}
    for det in detections:
        if 0 <= det.index < len(ohlcv):
            grouped.setdefault(det.bias, []).append(det)

    for bias, dets in grouped.items():
        if not dets:
            continue
        xs: list[str] = []
        ys: list[float] = []
        hover: list[str] = []
        symbols: list[str] = []
        for det in dets:
            bar = ohlcv[det.index]
            hi = float(bar.get("High") or 0.0)
            lo = float(bar.get("Low") or 0.0)
            # bullish / neutral → marker below low; bearish → above high
            if bias == "bearish":
                y = hi + offset
                sym = "triangle-down"
            elif bias == "bullish":
                y = lo - offset
                sym = "triangle-up"
            else:
                y = lo - offset
                sym = "circle"
            xs.append(str(bar.get("Date") or ""))
            ys.append(y)
            symbols.append(sym)
            hover.append(
                f"<b>{_pretty_pattern(det.pattern)}</b><br>"
                f"{det.date}<br>"
                f"Bias: {det.bias}<br>"
                f"Confidence: {det.confidence:.0%}<br>"
                f"{det.note}"
            )
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                name=f"{bias.title()} patterns",
                marker=dict(
                    size=12,
                    color=_BIAS_COLOR.get(bias, "#64748b"),
                    symbol=symbols,
                    line=dict(color="#0f172a", width=1),
                ),
                hovertemplate="%{text}<extra></extra>",
                text=hover,
            )
        )

    # Title
    bits = []
    if company_name:
        bits.append(company_name)
    if ticker:
        bits.append(f"({ticker})")
    if timeframe:
        bits.append(f"· {timeframe}")
    title = " ".join(bits) if bits else "Candlestick chart"

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        height=520,
        margin=dict(l=30, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    # Hide weekend gaps where possible (only works when dates are true dates)
    fig.update_xaxes(type="category")

    return fig


def build_detection_focus_figure(
    ohlcv: list[dict[str, Any]],
    detection: CandleDetection,
    window: int = 10,
) -> go.Figure:
    """Zoomed candlestick centered on a single detection, for the lesson UI."""
    if not ohlcv or not (0 <= detection.index < len(ohlcv)):
        return go.Figure()
    lo = max(0, detection.index - window)
    hi = min(len(ohlcv), detection.index + window + 1)
    sliced = ohlcv[lo:hi]
    # Re-index the detection into the slice
    shifted = CandleDetection(
        pattern=detection.pattern,
        index=detection.index - lo,
        date=detection.date,
        bias=detection.bias,
        confidence=detection.confidence,
        note=detection.note,
    )
    fig = build_candlestick_figure(sliced, [shifted])
    fig.update_layout(
        title=f"{_pretty_pattern(detection.pattern)} on {detection.date}",
        height=360,
    )
    return fig
