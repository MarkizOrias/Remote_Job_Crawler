"""Common database queries: insert, upsert, search, filter, stats."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.db.connection import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scrape runs
# ---------------------------------------------------------------------------

def start_scrape_run(conn: sqlite3.Connection, source: str) -> int:
    """Record the start of a scrape run. Returns the run ID."""
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO scrape_runs (source, started_at) VALUES (?, ?)",
        (source, now),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def finish_scrape_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    jobs_found: int = 0,
    jobs_new: int = 0,
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    """Mark a scrape run as finished."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE scrape_runs
           SET finished_at = ?, jobs_found = ?, jobs_new = ?,
               status = ?, error_message = ?
           WHERE id = ?""",
        (now, jobs_found, jobs_new, status, error_message, run_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Job insert / upsert
# ---------------------------------------------------------------------------

def upsert_job(conn: sqlite3.Connection, job_data: dict[str, Any]) -> bool:
    """Insert a job or update date_scraped if dedup_hash exists.

    Returns True if a new row was inserted, False if updated.
    """
    dedup_hash = job_data.get("dedup_hash")
    if dedup_hash:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE dedup_hash = ?", (dedup_hash,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE jobs SET date_scraped = ?, is_active = 1 WHERE id = ?",
                (job_data["date_scraped"], existing["id"]),
            )
            conn.commit()
            return False

    tags_json = json.dumps(job_data.get("tags", []))
    raw_json = json.dumps(job_data.get("raw_data")) if job_data.get("raw_data") else None

    conn.execute(
        """INSERT OR IGNORE INTO jobs
           (external_id, source, title, company, company_url, description,
            url, location, salary_min, salary_max, salary_currency,
            tags, job_type, experience_level, date_posted, date_scraped,
            dedup_hash, raw_data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_data.get("external_id"),
            job_data["source"],
            job_data["title"],
            job_data["company"],
            job_data.get("company_url"),
            job_data.get("description"),
            job_data["url"],
            job_data.get("location"),
            job_data.get("salary_min"),
            job_data.get("salary_max"),
            job_data.get("salary_currency", "USD"),
            tags_json,
            job_data.get("job_type"),
            job_data.get("experience_level"),
            job_data.get("date_posted"),
            job_data["date_scraped"],
            dedup_hash,
            raw_json,
        ),
    )
    conn.commit()
    return True


def bulk_upsert_jobs(
    conn: sqlite3.Connection, jobs: list[dict[str, Any]]
) -> tuple[int, int]:
    """Upsert a batch of jobs. Returns (total, new_count)."""
    new_count = 0
    for job_data in jobs:
        if upsert_job(conn, job_data):
            new_count += 1
    return len(jobs), new_count


# ---------------------------------------------------------------------------
# Company insert
# ---------------------------------------------------------------------------

def upsert_company(conn: sqlite3.Connection, company: dict[str, Any]) -> None:
    """Insert or update a company record."""
    tech_json = json.dumps(company.get("tech_stack", []))
    conn.execute(
        """INSERT INTO companies (name, website, careers_url, description,
                                  size, remote_policy, tech_stack, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               website = COALESCE(excluded.website, companies.website),
               careers_url = COALESCE(excluded.careers_url, companies.careers_url),
               description = COALESCE(excluded.description, companies.description),
               size = COALESCE(excluded.size, companies.size),
               remote_policy = COALESCE(excluded.remote_policy, companies.remote_policy),
               tech_stack = COALESCE(excluded.tech_stack, companies.tech_stack),
               source = COALESCE(excluded.source, companies.source)""",
        (
            company["name"],
            company.get("website"),
            company.get("careers_url"),
            company.get("description"),
            company.get("size"),
            company.get("remote_policy"),
            tech_json,
            company.get("source"),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Search & filter
# ---------------------------------------------------------------------------

def search_jobs(
    conn: sqlite3.Connection,
    *,
    query: str | None = None,
    source: str | None = None,
    remote_only: bool = False,
    salary_min: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search jobs with optional filters. Returns list of dicts."""
    clauses: list[str] = ["is_active = 1"]
    params: list[Any] = []

    if query:
        clauses.append("(title LIKE ? OR description LIKE ? OR tags LIKE ?)")
        wild = f"%{query}%"
        params.extend([wild, wild, wild])
    if source:
        clauses.append("source = ?")
        params.append(source)
    if remote_only:
        clauses.append("location LIKE '%remote%'")
    if salary_min is not None:
        clauses.append("salary_max >= ?")
        params.append(salary_min)

    where = " AND ".join(clauses)
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM jobs WHERE {where} ORDER BY date_scraped DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return summary statistics about the jobs database."""
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active = 1").fetchone()[0]
    by_source = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM jobs WHERE is_active = 1 GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    top_companies = conn.execute(
        "SELECT company, COUNT(*) as cnt FROM jobs WHERE is_active = 1 GROUP BY company ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    latest_run = conn.execute(
        "SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()

    return {
        "total_active_jobs": total,
        "by_source": {r["source"]: r["cnt"] for r in by_source},
        "top_companies": {r["company"]: r["cnt"] for r in top_companies},
        "latest_run": dict(latest_run) if latest_run else None,
    }


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def mark_stale(conn: sqlite3.Connection, older_than_days: int = 30) -> int:
    """Mark jobs not seen in the last N days as inactive. Returns count."""
    cutoff = datetime.now(timezone.utc)
    from datetime import timedelta
    cutoff_str = (cutoff - timedelta(days=older_than_days)).isoformat()
    cur = conn.execute(
        "UPDATE jobs SET is_active = 0 WHERE date_scraped < ? AND is_active = 1",
        (cutoff_str,),
    )
    conn.commit()
    return cur.rowcount
