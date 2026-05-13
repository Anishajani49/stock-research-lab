"""Streamlit dashboard — two modes: Stock Analysis and Candlestick Learning."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from app.adapters import mfapi  # noqa: E402
from app.analysis.stance import STANCE_PRETTY  # noqa: E402
from app.orchestrator import run as orch_run, run_learn  # noqa: E402
from app.reports.render_learning import render_lesson, save_lesson  # noqa: E402
from app.reports.render_markdown import render, save_report  # noqa: E402
from app.schemas.input import ResearchRequest  # noqa: E402
from app.ui.charts import (  # noqa: E402
    build_candlestick_figure,
    build_detection_focus_figure,
)


st.set_page_config(
    page_title="India Stock Research + Candlestick Learning",
    page_icon="🇮🇳",
    layout="wide",
)

st.title("🇮🇳 Indian Stock Research Assistant")
st.caption(
    "Local-first · NSE/BSE + Mutual Funds · deterministic stance engine · "
    "Ollama explains the reasoning · evidence-cited."
)

# -----------------------------------------------------------------------------
# Top-level mode selector (the two modes required by the refactor spec)

mode_tab, learn_tab = st.tabs(["🧭 Stock Analysis", "🕯️ Candlestick Learning"])


# =============================================================================
# STOCK ANALYSIS MODE
# =============================================================================

with mode_tab:
    st.subheader("Mode 1 — Stock Analysis")
    st.caption(
        "Deterministic stance engine decides the leaning (one of 5). "
        "The LLM only **explains** the decision using the evidence."
    )

    with st.sidebar:
        st.header("Analysis inputs")
        instrument = st.radio(
            "Instrument type",
            options=["Equity (NSE/BSE)", "Mutual Fund"],
            horizontal=False,
            index=0,
            key="analyze_instrument",
        )
        is_mf = instrument.startswith("Mutual")

        ticker_value: str = ""
        scheme_code: str | None = None
        exchange = "auto"

        if is_mf:
            search_query = st.text_input(
                "Search mutual fund (name or scheme code)",
                value="",
                placeholder="e.g. 'axis bluechip' or '120586'",
                key="analyze_mf_q",
            )
            if search_query.strip():
                with st.spinner("Searching AMFI..."):
                    hits = mfapi.search_scheme(search_query, limit=25)
                if hits:
                    options = {
                        f"{h.get('schemeName')}  ·  code {h.get('schemeCode')}": str(h.get("schemeCode"))
                        for h in hits
                    }
                    picked = st.selectbox("Select scheme", options=list(options.keys()), key="analyze_mf_pick")
                    if picked:
                        scheme_code = options[picked]
                        ticker_value = scheme_code
                else:
                    if search_query.strip().isdigit():
                        ticker_value = search_query.strip()
                        scheme_code = ticker_value
                    else:
                        st.warning("No schemes matched.")
        else:
            ticker_value = st.text_input(
                "Ticker",
                value="RELIANCE",
                placeholder="e.g. RELIANCE, TCS.NS, INFY.BO",
                key="analyze_ticker",
            ).strip().upper()
            exchange = st.selectbox("Exchange", options=["auto", "NSE", "BSE"], index=0, key="analyze_exch")

        timeframe = st.selectbox(
            "Timeframe",
            options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd"],
            index=2,
            key="analyze_tf",
        )
        st.caption(
            "📊 The chart is fetched automatically — no upload needed. "
            "Use the **Candlestick Learning** tab if you want to see and "
            "learn the chart in detail."
        )
        yt_text = st.text_area("YouTube URLs (one per line, optional)", key="analyze_yt")
        no_llm = st.checkbox("Skip LLM (deterministic only)", value=False, key="analyze_nollm")
        submit_analyze = st.button("Run analysis", type="primary", use_container_width=True, key="analyze_go")

    if submit_analyze:
        if not ticker_value:
            st.error("Please provide a ticker or MF scheme.")
            st.stop()

        yt_urls = [u.strip() for u in (yt_text or "").splitlines() if u.strip()]

        try:
            request = ResearchRequest(
                ticker=ticker_value,
                mode="analyze",
                instrument_type="mutual_fund" if is_mf else "equity",
                exchange=exchange,
                timeframe=timeframe,
                mf_scheme_code=scheme_code,
                chart_image=None,
                youtube_urls=yt_urls,
            )
        except Exception as e:
            st.error(f"Invalid input: {e}")
            st.stop()

        if no_llm:
            from app.llm import synthesis as _s

            def _skip(state, client=None):  # noqa: ARG001
                return _s._fallback_explanation(state, reason="skip-llm toggle")

            _s.synthesize = _skip  # type: ignore[assignment]

        label = "MF" if is_mf else exchange
        with st.spinner(f"Analyzing {ticker_value} [{label}, {timeframe}]..."):
            state = orch_run(request)

        # Top metrics
        col1, col2, col3, col4 = st.columns(4)
        snap = state.indicators
        currency = state.company_meta.get("currency") or "INR"
        symbol = "₹" if currency == "INR" else ""
        col1.metric(
            "Last NAV" if is_mf else "Last Close",
            f"{symbol}{snap.last_close:,.2f}" if snap.last_close else "n/a",
        )
        col2.metric("Trend", state.trend)
        col3.metric(
            "Stance",
            STANCE_PRETTY.get(state.stance.label, state.stance.label),
            delta=f"{state.stance.score:+.2f}",
        )
        col4.metric("Confidence", state.confidence, delta=f"{state.confidence_score:.2f}")

        if state.missing:
            st.warning("⚠️ Missing data: " + ", ".join(state.missing))

        # News coverage summary
        if state.headlines:
            src_counts: dict[str, int] = {}
            for h in state.headlines:
                s = h.get("source") or "Unknown"
                src_counts[s] = src_counts.get(s, 0) + 1
            summary = " · ".join(
                f"**{k}**: {v}" for k, v in sorted(src_counts.items(), key=lambda kv: -kv[1])
            )
            st.caption(f"News coverage — {summary}")

        md = render(state)

        subtabs = st.tabs(["📄 Report", "📰 Developments", "📈 Indicators", "🔎 Raw State"])
        with subtabs[0]:
            st.markdown(md)
            path = save_report(state, md)
            st.success(f"Saved to `{path}`")
        with subtabs[1]:
            if state.developments:
                rows = []
                for ev in state.developments:
                    rows.append({
                        "evidence_ids": ", ".join(ev.evidence_ids),
                        "category": ev.category,
                        "polarity": ev.polarity,
                        "importance": ev.importance,
                        "ticker_match": round(ev.ticker_match, 2),
                        "age_days": ev.age_days,
                        "source": ev.source,
                        "title": ev.title,
                    })
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No structured developments were extracted.")
        with subtabs[2]:
            st.json(snap.model_dump())
        with subtabs[3]:
            st.json(state.model_dump(mode="json"))


# =============================================================================
# CANDLESTICK LEARNING MODE
# =============================================================================

with learn_tab:
    st.subheader("Mode 2 — Candlestick Learning")
    st.caption(
        "An educational walk-through of candlestick charts. "
        "No trade signals — we pull a real chart for your ticker, mark the textbook "
        "patterns we can find on it, and explain what each one means. "
        "No uploads — the chart is fetched for you."
    )

    lcol1, lcol2, lcol3 = st.columns([2, 1, 1])
    with lcol1:
        learn_ticker = st.text_input(
            "Ticker to chart + explain",
            value="RELIANCE",
            placeholder="e.g. RELIANCE, TCS.NS, INFY.BO",
            key="learn_ticker",
        ).strip().upper()
    with lcol2:
        learn_tf = st.selectbox(
            "Timeframe",
            options=["3mo", "6mo", "1y", "2y"],
            index=1,
            key="learn_tf",
        )
    with lcol3:
        learn_exch = st.selectbox("Exchange", options=["auto", "NSE", "BSE"], index=0, key="learn_exch")

    submit_learn = st.button("Build lesson", type="primary", key="learn_go")

    if submit_learn:
        try:
            lreq = ResearchRequest(
                ticker=learn_ticker or "RELIANCE",
                mode="learn",
                instrument_type="equity",
                exchange=learn_exch,
                timeframe=learn_tf,
            )
        except Exception as e:
            st.error(f"Invalid input: {e}")
            st.stop()

        with st.spinner("Fetching chart and building candlestick lesson..."):
            lesson = run_learn(lreq)
        md = render_lesson(lesson)

        ltabs = st.tabs(["📊 Chart", "📖 Lesson", "📍 Detections", "🔎 Raw Lesson"])

        # --- 📊 Chart tab: the main ask — show the chart + explain it ---
        with ltabs[0]:
            if not lesson.ohlcv:
                st.error(
                    "Could not fetch price data for this ticker. "
                    "Try a different ticker or exchange (NSE/BSE)."
                )
            else:
                header_bits = []
                if lesson.company_name:
                    header_bits.append(f"**{lesson.company_name}**")
                if lesson.ticker:
                    header_bits.append(f"`{lesson.ticker}`")
                header_bits.append(f"{lesson.timeframe} · {lesson.n_bars} bars")
                if lesson.last_close:
                    header_bits.append(f"last close **{lesson.last_close:,.2f}**")
                st.markdown(" · ".join(header_bits))

                fig = build_candlestick_figure(
                    lesson.ohlcv,
                    lesson.detections,
                    ticker=lesson.ticker,
                    company_name=lesson.company_name,
                    timeframe=lesson.timeframe,
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### What this chart is showing")
                st.markdown(lesson.chart_summary or "_(chart summary unavailable)_")

                if lesson.detections:
                    st.markdown("#### Zoom into a specific pattern")
                    options = {
                        f"{d.date} — {d.pattern.replace('_', ' ').title()} "
                        f"({d.bias}, conf {d.confidence:.0%})": i
                        for i, d in enumerate(lesson.detections)
                    }
                    pick = st.selectbox(
                        "Pick a detection to zoom in",
                        options=list(options.keys()),
                        key="learn_pick_det",
                    )
                    if pick:
                        det = lesson.detections[options[pick]]
                        focus_fig = build_detection_focus_figure(lesson.ohlcv, det)
                        st.plotly_chart(focus_fig, use_container_width=True)
                        st.info(det.note)
                else:
                    st.caption(
                        "No textbook-grade patterns were detected — that's normal. "
                        "Real charts are noisy. Try a longer timeframe."
                    )

        with ltabs[1]:
            st.markdown(md)
            path = save_lesson(lesson, md)
            st.success(f"Lesson saved to `{path}`")
        with ltabs[2]:
            if lesson.detections:
                rows = [
                    {
                        "date": d.date,
                        "pattern": d.pattern,
                        "bias": d.bias,
                        "confidence": d.confidence,
                        "note": d.note,
                    }
                    for d in lesson.detections
                ]
                st.dataframe(rows, use_container_width=True)
            else:
                st.info(
                    "No textbook-grade patterns were detected in this window. "
                    "Try a longer timeframe or a different ticker."
                )
        with ltabs[3]:
            st.json(lesson.model_dump(mode="json"))
    else:
        st.info(
            "Pick a ticker (or just hit **Build lesson**) to get the full beginner "
            "walk-through of candlestick anatomy, single-candle patterns "
            "(doji / hammer / shooting star / marubozu) and multi-candle patterns "
            "(engulfing / morning star / evening star / harami) — plus confirmation "
            "logic and why context, volume, and support/resistance matter."
        )
