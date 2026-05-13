"""Annual-report adapter — fetch + extract text from a PDF URL or uploaded bytes.

We intentionally keep this small and dependency-light: pypdf for text
extraction, httpx for the download, a page-cap for safety. Scanned-image PDFs
(no embedded text) are handled gracefully — we return empty text and the
analyzer falls back to a 'this looks like a scanned PDF' message.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
    _PDF_OK = True
except Exception:
    _PDF_OK = False


_MAX_PAGES = 250          # cap — most Indian annual reports are 150-300 pages
_MAX_BYTES = 60 * 1024 * 1024  # 60 MB upper limit
_HTTP_TIMEOUT = 30.0


def fetch_pdf_from_url(url: str) -> dict[str, Any]:
    """Download a PDF from a URL. Returns {ok, error, bytes, content_type}."""
    out: dict[str, Any] = {"ok": False, "error": None, "bytes": None, "content_type": None}
    if not url or not url.lower().startswith(("http://", "https://")):
        out["error"] = "URL must start with http:// or https://"
        return out

    headers = {
        # Some IR sites block default Python UA — pretend to be a normal browser.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*",
    }
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True, headers=headers) as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.content
            if len(data) > _MAX_BYTES:
                out["error"] = f"PDF is too large ({len(data)/1e6:.0f} MB; cap is {_MAX_BYTES/1e6:.0f} MB)."
                return out
            ct = (r.headers.get("content-type") or "").lower()
            if "pdf" not in ct and not data[:4] == b"%PDF":
                out["error"] = (
                    "URL did not return a PDF. Check the link — many IR pages link to an HTML wrapper; "
                    "right-click the PDF download link and use that direct URL."
                )
                return out
            out["ok"] = True
            out["bytes"] = data
            out["content_type"] = ct
            return out
    except httpx.HTTPStatusError as e:
        out["error"] = f"Download failed with HTTP {e.response.status_code}."
    except httpx.HTTPError as e:
        out["error"] = f"Could not reach the URL: {e!s}"
    except Exception as e:
        out["error"] = f"Unexpected error fetching PDF: {e!s}"
    return out


def extract_text(pdf_bytes: bytes, max_pages: int = _MAX_PAGES) -> dict[str, Any]:
    """Extract text from a PDF bytes blob. Returns {ok, error, text, n_pages, n_pages_read, pages}."""
    out: dict[str, Any] = {
        "ok": False, "error": None,
        "text": "", "n_pages": 0, "n_pages_read": 0,
        "pages": [],
    }
    if not _PDF_OK:
        out["error"] = "pypdf is not installed."
        return out
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        n = len(reader.pages)
        out["n_pages"] = n
        limit = min(n, max_pages)
        chunks: list[str] = []
        pages: list[dict[str, Any]] = []
        for i in range(limit):
            try:
                t = reader.pages[i].extract_text() or ""
            except Exception as e:
                log.debug("page %d extract failed: %s", i, e)
                t = ""
            chunks.append(t)
            pages.append({"page": i + 1, "len": len(t)})
        full = "\n\n".join(chunks)
        out["ok"] = True
        out["text"] = full
        out["n_pages_read"] = limit
        out["pages"] = pages
        if not full.strip():
            # PDF had no extractable text — likely scanned images
            out["error"] = (
                "We could not extract any text from this PDF. It looks like a scanned-image PDF. "
                "Try a different report — most listed Indian companies publish a text-based version too."
            )
            out["ok"] = False
        return out
    except Exception as e:
        log.error("pypdf extract failed: %s", e)
        out["error"] = f"Could not parse the PDF: {e!s}"
        return out
