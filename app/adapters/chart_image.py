"""Chart image OCR — best-effort parsing of visible text."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

try:
    from PIL import Image  # noqa: F401
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

try:
    import pytesseract  # noqa: F401
    _TESS_AVAILABLE = True
except Exception:
    _TESS_AVAILABLE = False


_PRICE_RE = re.compile(r"\b\d{1,6}(?:[.,]\d{1,4})?\b")
_DATE_RE = re.compile(
    r"\b(?:20\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s?\d{0,4})\b",
    re.IGNORECASE,
)


def parse_chart(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    result: dict[str, Any] = {
        "ok": False, "error": None, "path": str(path),
        "raw_text": "", "price_labels": [], "time_labels": [], "summary": "",
    }

    if not settings.ENABLE_CHART_OCR:
        result["error"] = "Chart OCR disabled via ENABLE_CHART_OCR=false"
        return result
    if not path.exists():
        result["error"] = f"File not found: {path}"
        return result
    if not _PIL_AVAILABLE:
        result["error"] = "Pillow not installed"
        return result
    if not _TESS_AVAILABLE:
        result["error"] = "pytesseract not installed (and Tesseract binary required)"
        return result

    try:
        from PIL import Image
        import pytesseract

        img = Image.open(path)
        text = pytesseract.image_to_string(img) or ""
    except pytesseract.TesseractNotFoundError:
        result["error"] = "Tesseract binary not found. Install via: brew install tesseract"
        return result
    except Exception as e:
        log.warning("Chart OCR failed: %s", e)
        result["error"] = f"OCR failed: {e!s}"
        return result

    prices = sorted({m.group(0) for m in _PRICE_RE.finditer(text)})
    dates = sorted({m.group(0) for m in _DATE_RE.finditer(text)})

    summary_parts = []
    if prices:
        summary_parts.append(f"detected {len(prices)} numeric labels (possible price ticks)")
    if dates:
        summary_parts.append(f"detected {len(dates)} date-like tokens")
    if not summary_parts:
        summary_parts.append("no structured labels confidently detected")

    result.update({
        "ok": True,
        "raw_text": text[:4000],
        "price_labels": prices[:40],
        "time_labels": dates[:40],
        "summary": "; ".join(summary_parts),
    })
    return result
