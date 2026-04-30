"""Export jobs to Markdown."""

import sqlite3
from pathlib import Path


def export_markdown(conn: sqlite3.Connection, output: Path, *, query: str | None = None, limit: int = 200) -> int:
    """Export active jobs to a Markdown table. Returns row count."""
    clauses = ["is_active = 1"]
    params: list = []

    if query:
        clauses.append("(title LIKE ? OR company LIKE ? OR tags LIKE ?)")
        wild = f"%{query}%"
        params.extend([wild, wild, wild])

    params.append(limit)
    where = " AND ".join(clauses)

    rows = conn.execute(
        f"""SELECT title, company, location, salary_min, salary_max, source, url
            FROM jobs WHERE {where} ORDER BY date_scraped DESC LIMIT ?""",
        params,
    ).fetchall()

    if not rows:
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Job Listings ({len(rows)} results)\n",
        "| Title | Company | Location | Salary | Source |",
        "|-------|---------|----------|--------|--------|",
    ]

    for r in rows:
        salary = ""
        if r["salary_min"] or r["salary_max"]:
            lo = f"${r['salary_min']:,}" if r["salary_min"] else "?"
            hi = f"${r['salary_max']:,}" if r["salary_max"] else "?"
            salary = f"{lo}–{hi}"
        title_link = f"[{r['title']}]({r['url']})"
        lines.append(f"| {title_link} | {r['company']} | {r['location'] or '—'} | {salary} | {r['source']} |")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)
