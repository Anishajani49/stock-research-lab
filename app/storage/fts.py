"""FTS5 full-text search over evidence."""

from __future__ import annotations

from pathlib import Path

from app.storage.db import connection, init_db


def search(query: str, limit: int = 20, db_path: Path | None = None) -> list[dict]:
    """Search evidence by FTS5 MATCH query. Falls back to LIKE on malformed queries."""
    if not query.strip():
        return []
    init_db(db_path)
    safe_query = query.replace('"', '""')
    sql_fts = (
        "SELECT e.* FROM evidence_fts f "
        "JOIN evidence e ON e.evidence_id = f.evidence_id "
        "WHERE evidence_fts MATCH ? "
        "ORDER BY rank LIMIT ?"
    )
    with connection(db_path) as conn:
        try:
            cur = conn.execute(sql_fts, (safe_query, limit))
            return [dict(r) for r in cur.fetchall()]
        except Exception:
            # Fallback: simple LIKE
            like = f"%{query}%"
            cur = conn.execute(
                "SELECT * FROM evidence WHERE title LIKE ? OR snippet LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (like, like, limit),
            )
            return [dict(r) for r in cur.fetchall()]
