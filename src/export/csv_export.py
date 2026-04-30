"""Export jobs to CSV."""

import csv
import sqlite3
from pathlib import Path


def export_csv(conn: sqlite3.Connection, output: Path, *, query: str | None = None, limit: int = 5000) -> int:
    """Export active jobs to a CSV file. Returns row count."""
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
    columns = rows[0].keys()

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    return len(rows)
