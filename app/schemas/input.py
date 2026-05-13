"""Input schemas for the orchestrator (India-focused)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


InstrumentType = Literal["equity", "mutual_fund"]
Exchange = Literal["NSE", "BSE", "auto"]
Mode = Literal["analyze", "learn"]


class ResearchRequest(BaseModel):
    ticker: str = Field(
        ...,
        description=(
            "For equity: NSE/BSE symbol (e.g. 'RELIANCE', 'RELIANCE.NS', 'TCS.BO'). "
            "For mutual funds: AMFI scheme code (e.g. '120586') or scheme name. "
            "In learn mode: optional — used to pull real candles for examples."
        ),
    )
    mode: Mode = "analyze"
    instrument_type: InstrumentType = "equity"
    exchange: Exchange = "auto"
    timeframe: str = Field("6mo", description="e.g. 1mo, 3mo, 6mo, 1y, 2y, 5y")
    mf_scheme_code: Optional[str] = Field(
        None, description="AMFI numeric scheme code (if already known)"
    )
    chart_image: Optional[Path] = None
    youtube_urls: list[str] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def _clean_ticker(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ticker must not be empty")
        return v

    @field_validator("timeframe")
    @classmethod
    def _valid_timeframe(cls, v: str) -> str:
        allowed = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"timeframe must be one of {sorted(allowed)}")
        return v

    @field_validator("exchange")
    @classmethod
    def _upper_exchange(cls, v: str) -> str:
        return v.strip().upper() if v else "auto"

    @property
    def is_mutual_fund(self) -> bool:
        return self.instrument_type == "mutual_fund"

    @property
    def is_learn_mode(self) -> bool:
        return self.mode == "learn"
