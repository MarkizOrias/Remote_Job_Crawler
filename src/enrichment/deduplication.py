"""Deduplication: hash-based primary check, fuzzy secondary check."""

import hashlib
import logging
import sqlite3

from thefuzz import fuzz

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85


def make_dedup_hash(title: str, company: str) -> str:
    """Generate a dedup hash from normalized title + company."""
    normalized = f"{title.lower().strip()}|{company.lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def find_fuzzy_duplicates(
    conn: sqlite3.Connection,
    title: str,
    company: str,
    *,
    threshold: int = FUZZY_THRESHOLD,
) -> list[dict]:
    """Check for near-duplicate jobs using fuzzy string matching.

    Returns existing jobs that exceed the similarity threshold.
    """
    candidates = conn.execute(
        "SELECT id, title, company, source, url FROM jobs WHERE company LIKE ? AND is_active = 1",
        (f"%{company.strip()[:20]}%",),
    ).fetchall()

    target = f"{title.lower().strip()} | {company.lower().strip()}"
    dupes: list[dict] = []

    for row in candidates:
        candidate = f"{row['title'].lower().strip()} | {row['company'].lower().strip()}"
        score = fuzz.token_sort_ratio(target, candidate)
        if score >= threshold:
            dupes.append({
                "id": row["id"],
                "title": row["title"],
                "company": row["company"],
                "source": row["source"],
                "url": row["url"],
                "similarity": score,
            })

    return dupes


def deduplicate_jobs(
    conn: sqlite3.Connection,
    jobs: list[dict],
    *,
    threshold: int = FUZZY_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """Split jobs into unique and duplicate lists.

    First checks by dedup_hash (exact), then by fuzzy match.
    Returns (unique_jobs, duplicate_jobs).
    """
    unique: list[dict] = []
    duplicates: list[dict] = []

    for job in jobs:
        dedup_hash = job.get("dedup_hash") or make_dedup_hash(job["title"], job["company"])

        existing = conn.execute(
            "SELECT id FROM jobs WHERE dedup_hash = ?", (dedup_hash,)
        ).fetchone()

        if existing:
            duplicates.append(job)
            continue

        fuzzy_matches = find_fuzzy_duplicates(
            conn, job["title"], job["company"], threshold=threshold,
        )
        if fuzzy_matches:
            logger.debug(
                "Fuzzy duplicate: '%s @ %s' matches '%s @ %s' (score=%d)",
                job["title"], job["company"],
                fuzzy_matches[0]["title"], fuzzy_matches[0]["company"],
                fuzzy_matches[0]["similarity"],
            )
            duplicates.append(job)
        else:
            unique.append(job)

    logger.info(
        "Dedup result: %d unique, %d duplicates out of %d total",
        len(unique), len(duplicates), len(jobs),
    )
    return unique, duplicates
