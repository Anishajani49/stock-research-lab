"""Simple JSON file cache for raw adapter responses."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.config import settings


# macOS + ext4 cap filenames at 255 bytes; keep a safety margin.
_MAX_FILENAME_LEN = 180


def _key_path(namespace: str, key: str) -> Path:
    safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    # If the sanitized key would produce an overly long filename, hash it.
    if len(safe_key) + len(".json") > _MAX_FILENAME_LEN:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        # Keep a short readable prefix so cache files are still debuggable.
        prefix = safe_key[:60].rstrip("_")
        safe_key = f"{prefix}__{digest}"
    d = settings.CACHE_DIR / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe_key}.json"


def get(namespace: str, key: str, ttl_seconds: int = 3600) -> Any | None:
    path = _key_path(namespace, key)
    if not path.exists():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > ttl_seconds:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def set(namespace: str, key: str, value: Any) -> None:  # noqa: A001
    path = _key_path(namespace, key)
    try:
        path.write_text(json.dumps(value, default=str, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
