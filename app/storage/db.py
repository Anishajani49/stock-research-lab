"""SQLite evidence store with FTS5 virtual table."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from app.config import settings
from app.schemas.evidence import Evidence


SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    snippet TEXT,
    timestamp TEXT NOT NULL,
    quality_score REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
    evidence_id UNINDEXED,
    title,
    snippet,
    url UNINDEXED,
    content='evidence',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence BEGIN
  INSERT INTO evidence_fts(rowid, evidence_id, title, snippet, url)
  VALUES (new.rowid, new.evidence_id, new.title, new.snippet, new.url);
END;

CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence BEGIN
  INSERT INTO evidence_fts(evidence_fts, rowid, evidence_id, title, snippet, url)
  VALUES ('delete', old.rowid, old.evidence_id, old.title, old.snippet, old.url);
END;

CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence BEGIN
  INSERT INTO evidence_fts(evidence_fts, rowid, evidence_id, title, snippet, url)
  VALUES ('delete', old.rowid, old.evidence_id, old.title, old.snippet, old.url);
  INSERT INTO evidence_fts(rowid, evidence_id, title, snippet, url)
  VALUES (new.rowid, new.evidence_id, new.title, new.snippet, new.url);
END;
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else settings.EVIDENCE_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def connection(db_path: Path | None = None):
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_evidence(items: Iterable[Evidence], db_path: Path | None = None) -> int:
    rows = [e.to_row() for e in items]
    if not rows:
        return 0
    init_db(db_path)
    with connection(db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO evidence "
            "(evidence_id, source_type, title, url, snippet, timestamp, quality_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def get_evidence(evidence_id: str, db_path: Path | None = None) -> dict | None:
    init_db(db_path)
    with connection(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def recent_evidence(limit: int = 50, db_path: Path | None = None) -> list[dict]:
    init_db(db_path)
    with connection(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM evidence ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]
