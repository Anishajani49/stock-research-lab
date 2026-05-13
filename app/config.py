"""Central configuration — loads from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


class Settings:
    # Paths
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
    CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", "./data/cache"))
    RAW_DIR: Path = Path(os.getenv("RAW_DIR", "./data/raw"))
    PROCESSED_DIR: Path = Path(os.getenv("PROCESSED_DIR", "./data/processed"))
    EVIDENCE_DB: Path = Path(os.getenv("EVIDENCE_DB", "./data/cache/evidence.sqlite"))

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    OLLAMA_TIMEOUT: int = _int("OLLAMA_TIMEOUT", 120)

    # HTTP
    HTTP_TIMEOUT: int = _int("HTTP_TIMEOUT", 15)
    HTTP_MAX_RETRIES: int = _int("HTTP_MAX_RETRIES", 3)

    # Defaults
    DEFAULT_TIMEFRAME: str = os.getenv("DEFAULT_TIMEFRAME", "6mo")
    NEWS_MAX_ITEMS: int = _int("NEWS_MAX_ITEMS", 15)
    ARTICLE_MAX_ITEMS: int = _int("ARTICLE_MAX_ITEMS", 5)

    # India defaults
    DEFAULT_EXCHANGE: str = os.getenv("DEFAULT_EXCHANGE", "NSE")  # NSE | BSE
    DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "INR")
    LOCALE_REGION: str = os.getenv("LOCALE_REGION", "IN")
    MFAPI_BASE_URL: str = os.getenv("MFAPI_BASE_URL", "https://api.mfapi.in")

    # Feature toggles
    ENABLE_CHART_OCR: bool = _bool("ENABLE_CHART_OCR", True)
    ENABLE_YOUTUBE: bool = _bool("ENABLE_YOUTUBE", True)

    @classmethod
    def ensure_dirs(cls) -> None:
        for p in (cls.DATA_DIR, cls.CACHE_DIR, cls.RAW_DIR, cls.PROCESSED_DIR):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
Settings.ensure_dirs()
