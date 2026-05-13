"""Candlestick pattern catalog — pure data, no detection logic.

Each pattern entry has:
  - name:        short key ("hammer", "bullish_engulfing")
  - display:     title-case name for UI
  - type:        "single" | "multi"
  - bias:        "bullish" | "bearish" | "neutral"
  - what_it_is:  plain-English description
  - what_it_may_suggest: what traders often read into it
  - when_it_matters: context that makes it meaningful
  - when_it_fails:   cases to ignore / that invalidate it
  - confirmation:    follow-through required before acting
  - example_ascii:   a tiny ASCII sketch to help beginners visualise
"""

from __future__ import annotations


ANATOMY: dict[str, object] = {
    "title": "Candle anatomy",
    "intro": (
        "A single candlestick shows 4 prices for a chosen period (1 day, 1 hour, etc): "
        "open, high, low, close. The thick part is the **body**. The thin lines above / "
        "below the body are **wicks** (also called shadows)."
    ),
    "diagram": r"""
       |        <- upper wick  (high)
       |
      ███       <- body top    (close for bullish, open for bearish)
      ███
      ███       <- body        (green/white = close > open, red/black = close < open)
      ███
      ███       <- body bottom (open for bullish, close for bearish)
       |
       |        <- lower wick  (low)
    """.strip("\n"),
    "notes": [
        "A **long body** means buyers OR sellers dominated the period.",
        "A **small body** means open and close were close together — indecision.",
        "A **long upper wick** means price pushed up but sellers drove it back.",
        "A **long lower wick** means price fell but buyers pushed it back up.",
    ],
}


BULLISH_VS_BEARISH: dict[str, object] = {
    "title": "Bullish vs bearish candles",
    "items": [
        {
            "kind": "Bullish candle",
            "what": "Close is higher than open. Drawn green or white (depending on platform).",
            "meaning": "Buyers were stronger than sellers during that period.",
        },
        {
            "kind": "Bearish candle",
            "what": "Close is lower than open. Drawn red or black.",
            "meaning": "Sellers were stronger than buyers during that period.",
        },
    ],
    "note": (
        "One candle on its own usually tells you very little. You need CONTEXT — "
        "where it appears in the current trend — before giving it any weight."
    ),
}


# -- Single-candle patterns ---------------------------------------------------

_SINGLE: list[dict[str, object]] = [
    {
        "name": "doji",
        "display": "Doji",
        "type": "single",
        "bias": "neutral",
        "what_it_is": (
            "A candle where open and close are almost equal (tiny body) with wicks on "
            "both sides. Looks like a '+' or a cross."
        ),
        "what_it_may_suggest": (
            "Indecision — buyers and sellers finished the period at roughly the same price. "
            "After a strong trend, this can hint the trend is tiring."
        ),
        "when_it_matters": (
            "When it appears AFTER a clear uptrend or downtrend — especially near a "
            "known support / resistance level."
        ),
        "when_it_fails": (
            "In a sideways, choppy market doji are everywhere and mean very little."
        ),
        "confirmation": (
            "Wait for the NEXT candle to break in the opposite direction of the prior "
            "trend before reading anything into the doji."
        ),
        "example_ascii": "|\n-+-\n|",
    },
    {
        "name": "hammer",
        "display": "Hammer",
        "type": "single",
        "bias": "bullish",
        "what_it_is": (
            "A small body (near the top of the candle) with a long lower wick (2x body "
            "or more) and little-to-no upper wick. Appears after a downtrend."
        ),
        "what_it_may_suggest": (
            "Sellers pushed price far down during the period, but buyers took over and "
            "pushed price back near the open. Possible trend reversal."
        ),
        "when_it_matters": (
            "After a clear downtrend, preferably touching a support level or a prior low."
        ),
        "when_it_fails": (
            "In the middle of a calm uptrend or a sideways range it's just normal noise."
        ),
        "confirmation": (
            "A higher close on the NEXT candle is usually required before trusting the signal."
        ),
        "example_ascii": "███\n███\n |\n |\n |",
    },
    {
        "name": "shooting_star",
        "display": "Shooting star",
        "type": "single",
        "bias": "bearish",
        "what_it_is": (
            "Small body near the bottom of the candle with a long upper wick (2x body or "
            "more) and little-to-no lower wick. Appears after an uptrend."
        ),
        "what_it_may_suggest": (
            "Buyers pushed price high but sellers drove it back down by the close. "
            "Possible trend reversal to the downside."
        ),
        "when_it_matters": (
            "After a clear uptrend, especially near a resistance level."
        ),
        "when_it_fails": (
            "After a sideways range it's rarely meaningful."
        ),
        "confirmation": (
            "A lower close on the NEXT candle adds weight to the reversal idea."
        ),
        "example_ascii": " |\n |\n |\n███\n███",
    },
    {
        "name": "marubozu_bullish",
        "display": "Bullish marubozu",
        "type": "single",
        "bias": "bullish",
        "what_it_is": (
            "A tall green/white candle with a big body and essentially NO wicks — open "
            "is the low, close is the high."
        ),
        "what_it_may_suggest": (
            "Strong, one-sided buying through the entire period. Often marks the start "
            "of a fresh up-leg."
        ),
        "when_it_matters": (
            "After a base / consolidation, or after a pullback inside an uptrend."
        ),
        "when_it_fails": (
            "At the end of an extended, overheated uptrend it can also be a late, "
            "exhausted move."
        ),
        "confirmation": (
            "Follow-through strength on the next day or two, ideally on rising volume."
        ),
        "example_ascii": "███\n███\n███\n███",
    },
    {
        "name": "marubozu_bearish",
        "display": "Bearish marubozu",
        "type": "single",
        "bias": "bearish",
        "what_it_is": (
            "A tall red/black candle with a big body and essentially NO wicks — open "
            "is the high, close is the low."
        ),
        "what_it_may_suggest": (
            "Strong, one-sided selling through the entire period."
        ),
        "when_it_matters": (
            "After a rally that is stalling, especially near a resistance level."
        ),
        "when_it_fails": (
            "After a long, steep downtrend it can mark a capitulation bottom instead."
        ),
        "confirmation": (
            "Follow-through weakness + bearish news context."
        ),
        "example_ascii": "▓▓▓\n▓▓▓\n▓▓▓\n▓▓▓",
    },
]


# -- Multi-candle patterns ----------------------------------------------------

_MULTI: list[dict[str, object]] = [
    {
        "name": "bullish_engulfing",
        "display": "Bullish engulfing",
        "type": "multi",
        "bias": "bullish",
        "what_it_is": (
            "Two candles: a small bearish candle followed by a bigger bullish candle "
            "whose body fully 'swallows' the prior body."
        ),
        "what_it_may_suggest": (
            "Buyers forcefully took over after a down session — potential reversal."
        ),
        "when_it_matters": (
            "After a downtrend, especially near a known support level."
        ),
        "when_it_fails": (
            "Mid-uptrend or in chop it's common and not meaningful."
        ),
        "confirmation": (
            "A higher close on the next candle + rising volume."
        ),
        "example_ascii": "▓▓▓ ███\n▓▓▓ ███\n    ███\n    ███",
    },
    {
        "name": "bearish_engulfing",
        "display": "Bearish engulfing",
        "type": "multi",
        "bias": "bearish",
        "what_it_is": (
            "Two candles: a small bullish candle followed by a bigger bearish candle "
            "whose body fully 'swallows' the prior body."
        ),
        "what_it_may_suggest": (
            "Sellers forcefully overtook buyers — potential top / reversal."
        ),
        "when_it_matters": (
            "After an uptrend, especially near resistance."
        ),
        "when_it_fails": (
            "Within a healthy uptrend that has rising-volume bullish days."
        ),
        "confirmation": (
            "A lower close the next session, ideally on heavier volume."
        ),
        "example_ascii": "███ ▓▓▓\n███ ▓▓▓\n    ▓▓▓\n    ▓▓▓",
    },
    {
        "name": "morning_star",
        "display": "Morning star",
        "type": "multi",
        "bias": "bullish",
        "what_it_is": (
            "Three candles: (1) a long bearish candle, (2) a small-bodied candle (the "
            "'star') that gaps lower, (3) a long bullish candle that closes well into "
            "the first candle's body."
        ),
        "what_it_may_suggest": (
            "Downtrend is losing steam and buyers have taken over — common reversal signal."
        ),
        "when_it_matters": (
            "At the end of a clear downtrend; stronger near a support level."
        ),
        "when_it_fails": (
            "If the third candle is weak, or if broader market/news is still negative."
        ),
        "confirmation": (
            "Follow-through on the next day + positive news / context."
        ),
        "example_ascii": "▓▓▓     ███\n▓▓▓     ███\n▓▓▓ -+- ███\n▓▓▓     ███",
    },
    {
        "name": "evening_star",
        "display": "Evening star",
        "type": "multi",
        "bias": "bearish",
        "what_it_is": (
            "Three candles: (1) a long bullish candle, (2) a small-bodied 'star' that "
            "gaps higher, (3) a long bearish candle that closes well into the first body."
        ),
        "what_it_may_suggest": (
            "Uptrend is losing steam and sellers have taken over — common topping signal."
        ),
        "when_it_matters": (
            "After a clear uptrend, especially near resistance."
        ),
        "when_it_fails": (
            "If the third candle is weak, or if news/flows remain strongly bullish."
        ),
        "confirmation": (
            "Follow-through weakness the next session."
        ),
        "example_ascii": "███     ▓▓▓\n███     ▓▓▓\n███ -+- ▓▓▓\n███     ▓▓▓",
    },
    {
        "name": "bullish_harami",
        "display": "Bullish harami",
        "type": "multi",
        "bias": "bullish",
        "what_it_is": (
            "Two candles: a big bearish candle followed by a small bullish candle whose "
            "body fits INSIDE the previous body."
        ),
        "what_it_may_suggest": (
            "Selling pressure paused — early sign of a possible reversal, but weaker "
            "than an engulfing."
        ),
        "when_it_matters": (
            "After a downtrend, near support."
        ),
        "when_it_fails": (
            "In a strong ongoing downtrend with negative news — may just be a pause."
        ),
        "confirmation": (
            "Needs a clearly bullish follow-up candle — not a standalone signal."
        ),
        "example_ascii": "▓▓▓\n▓▓▓ ███\n▓▓▓ ███\n▓▓▓",
    },
    {
        "name": "bearish_harami",
        "display": "Bearish harami",
        "type": "multi",
        "bias": "bearish",
        "what_it_is": (
            "Two candles: a big bullish candle followed by a small bearish candle whose "
            "body fits INSIDE the previous body."
        ),
        "what_it_may_suggest": (
            "Buying pressure paused — early sign of a possible top, weaker than a "
            "bearish engulfing."
        ),
        "when_it_matters": (
            "After an uptrend, near resistance."
        ),
        "when_it_fails": (
            "In a healthy uptrend with bullish news — may just be a pause."
        ),
        "confirmation": (
            "Needs a clearly bearish follow-up candle."
        ),
        "example_ascii": "███\n███ ▓▓▓\n███ ▓▓▓\n███",
    },
]


PATTERN_CATALOG: list[dict[str, object]] = _SINGLE + _MULTI


def get_pattern(name: str) -> dict[str, object] | None:
    for p in PATTERN_CATALOG:
        if p["name"] == name:
            return p
    return None


CONTEXT_NOTES: dict[str, object] = {
    "title": "Why context, volume, and support / resistance matter",
    "bullets": [
        (
            "**Trend context:** A bullish reversal pattern only means something after a "
            "downtrend. In a strong uptrend the same shape is usually noise."
        ),
        (
            "**Volume:** A pattern on high volume is far more trustworthy than the same "
            "shape on thin volume. Volume is the 'conviction' behind the move."
        ),
        (
            "**Support and resistance:** Patterns near a known support (price floor) or "
            "resistance (price ceiling) are more reliable. A hammer at support > a hammer in mid-air."
        ),
        (
            "**Confirmation:** Most patterns require the NEXT candle to close in the "
            "expected direction before you treat the signal as valid."
        ),
        (
            "**Timeframes:** A daily hammer and a 5-minute hammer are not equivalent. "
            "Longer timeframes produce stronger signals."
        ),
    ],
}
