"""Evidence record schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal[
    "market_data", "news_rss", "article", "youtube", "chart_image", "meta"
]


class Evidence(BaseModel):
    evidence_id: str
    source_type: SourceType
    title: str
    url: Optional[str] = None
    snippet: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality_score: float = 0.5  # 0.0 - 1.0

    def to_row(self) -> tuple:
        return (
            self.evidence_id,
            self.source_type,
            self.title,
            self.url or "",
            self.snippet,
            self.timestamp.isoformat(),
            float(self.quality_score),
        )
