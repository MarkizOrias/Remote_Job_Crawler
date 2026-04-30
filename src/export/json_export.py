"""Export jobs to JSON."""

import json
import sqlite3
from pathlib import Path


def export_json(conn: sqlite3.Connection, output: Path, *, query: str | None = None, limit: int = 5000) -> int:
    """Export active jobs to a JSON file. Returns row count."""
    clauses = ["is_active = 1"]
    params: list = []

    if query:
        clauses.append("(title LIKE ? OR company LIKE ? OR tags LIKE ?)")
        wild = f"%{query}%"
        params.extend([wild, wild, wild])

    params.append(limit)
    where = " AND ".join(clauses)

    rows = conn.execute(
        f"SELECT * FROM jobs WHERE {where} ORDER BY date_scraped DESC LIMIT ?",
        params,
    ).fetchall()

    if not rows:
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    data = [dict(r) for r in rows]

    output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(data)
