"""CLI entrypoint for the remote job scraper."""

import asyncio
import logging

import click

from src.config import setup_logging
from src.db.connection import get_connection, init_db
from src.db.queries import (
    bulk_upsert_jobs,
    finish_scrape_run,
    get_stats,
    mark_stale,
    search_jobs,
    start_scrape_run,
)
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SCRAPERS: dict[str, type[BaseScraper]] = {}


def _register_scrapers() -> None:
    from src.scrapers.remoteok import RemoteOKScraper
    from src.scrapers.remotive import RemotiveScraper
    from src.scrapers.weworkremotely import WeWorkRemotelyScraper
    from src.scrapers.startupjobs import StartupJobsScraper
    from src.scrapers.dayonejobs import DayOneJobsScraper
    from src.scrapers.wellfound import WellfoundScraper
    from src.scrapers.trueup import TrueUpScraper
    from src.scrapers.remotefirstjobs import RemoteFirstJobsScraper
    from src.scrapers.github_lists import GitHubListsScraper
    SCRAPERS["remoteok"] = RemoteOKScraper
    SCRAPERS["remotive"] = RemotiveScraper
    SCRAPERS["weworkremotely"] = WeWorkRemotelyScraper
    SCRAPERS["startupjobs"] = StartupJobsScraper
    SCRAPERS["dayonejobs"] = DayOneJobsScraper
    SCRAPERS["wellfound"] = WellfoundScraper
    SCRAPERS["trueup"] = TrueUpScraper
    SCRAPERS["remotefirstjobs"] = RemoteFirstJobsScraper
    SCRAPERS["github_lists"] = GitHubListsScraper


async def _run_scraper(scraper: BaseScraper) -> None:
    """Run a single scraper: fetch jobs, upsert into DB, track the run."""
    conn = get_connection()
    run_id = start_scrape_run(conn, scraper.name)

    try:
        jobs = await scraper.scrape()
        db_dicts = [j.to_db_dict() for j in jobs]
        total, new_count = bulk_upsert_jobs(conn, db_dicts)
        finish_scrape_run(conn, run_id, jobs_found=total, jobs_new=new_count)
        click.echo(f"  [{scraper.name}] {total} jobs found, {new_count} new")
    except Exception as exc:
        logger.error("[%s] Scraper failed: %s", scraper.name, exc, exc_info=True)
        finish_scrape_run(conn, run_id, status="failed", error_message=str(exc))
        click.echo(f"  [{scraper.name}] FAILED: {exc}")
    finally:
        await scraper.close()
        conn.close()


@click.group()
def cli() -> None:
    """Remote Startup Job Scraper."""
    setup_logging()
    init_db()
    _register_scrapers()


@cli.command()
@click.option("--all", "run_all", is_flag=True, help="Run all enabled scrapers")
@click.option("--source", type=str, default=None, help="Run a specific scraper by name")
def scrape(run_all: bool, source: str | None) -> None:
    """Scrape job listings from remote job boards."""
    if source:
        if source not in SCRAPERS:
            click.echo(f"Unknown source: {source}. Available: {', '.join(SCRAPERS)}")
            return
        targets = [source]
    elif run_all:
        targets = [name for name, cls in SCRAPERS.items() if cls().enabled]
    else:
        click.echo("Specify --all or --source <name>")
        return

    click.echo(f"Scraping {len(targets)} source(s)...")
    for name in targets:
        scraper = SCRAPERS[name]()
        asyncio.run(_run_scraper(scraper))
    click.echo("Done.")


@cli.command()
@click.argument("query")
@click.option("--remote-only", is_flag=True, help="Only remote positions")
@click.option("--salary-min", type=int, default=None, help="Minimum salary filter")
@click.option("--source", type=str, default=None, help="Filter by source")
@click.option("--limit", type=int, default=20, help="Max results")
def search(query: str, remote_only: bool, salary_min: int | None, source: str | None, limit: int) -> None:
    """Search scraped job listings."""
    conn = get_connection()
    results = search_jobs(conn, query=query, remote_only=remote_only, salary_min=salary_min, source=source, limit=limit)
    conn.close()

    if not results:
        click.echo("No matching jobs found.")
        return

    click.echo(f"Found {len(results)} result(s):\n")
    for r in results:
        salary = ""
        if r["salary_min"] or r["salary_max"]:
            lo = f"${r['salary_min']:,}" if r["salary_min"] else "?"
            hi = f"${r['salary_max']:,}" if r["salary_max"] else "?"
            salary = f"  [{lo} - {hi}]"
        click.echo(f"  {r['title']} @ {r['company']}{salary}")
        click.echo(f"    {r['url']}")
        click.echo(f"    Source: {r['source']}  |  Location: {r['location'] or '—'}")
        click.echo()


@cli.command()
def stats() -> None:
    """Show summary statistics."""
    conn = get_connection()
    s = get_stats(conn)
    conn.close()

    click.echo(f"Total active jobs: {s['total_active_jobs']}")
    click.echo("\nBy source:")
    for src, cnt in s["by_source"].items():
        click.echo(f"  {src}: {cnt}")
    click.echo("\nTop companies:")
    for comp, cnt in s["top_companies"].items():
        click.echo(f"  {comp}: {cnt}")
    if s["latest_run"]:
        r = s["latest_run"]
        click.echo(f"\nLatest run: {r['source']} — {r['status']} ({r['jobs_found']} found, {r['jobs_new']} new)")


@cli.command()
@click.option("--older-than", type=int, default=30, help="Days threshold")
def cleanup(older_than: int) -> None:
    """Mark stale listings as inactive."""
    conn = get_connection()
    count = mark_stale(conn, older_than)
    conn.close()
    click.echo(f"Marked {count} job(s) as inactive (not seen in {older_than}+ days).")


@cli.command(name="export")
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "markdown"]), required=True)
@click.option("--output", type=click.Path(), default=None, help="Output file path")
@click.option("--query", type=str, default=None, help="Filter by search query")
def export_cmd(fmt: str, output: str | None, query: str | None) -> None:
    """Export job listings to CSV, JSON, or Markdown."""
    from pathlib import Path
    from src.export.csv_export import export_csv
    from src.export.json_export import export_json
    from src.export.markdown_export import export_markdown

    default_names = {"csv": "jobs.csv", "json": "jobs.json", "markdown": "jobs.md"}
    out_path = Path(output) if output else Path("data") / default_names[fmt]

    conn = get_connection()
    exporters = {"csv": export_csv, "json": export_json, "markdown": export_markdown}
    count = exporters[fmt](conn, out_path, query=query)
    conn.close()

    if count:
        click.echo(f"Exported {count} job(s) to {out_path}")
    else:
        click.echo("No jobs matched the filters.")


@cli.command()
@click.option("--remote-first", is_flag=True, help="Only remote-first companies")
@click.option("--tech", type=str, default=None, help="Filter by tech stack keyword")
@click.option("--limit", type=int, default=30, help="Max results")
def companies(remote_first: bool, tech: str | None, limit: int) -> None:
    """List companies from GitHub directories."""
    conn = get_connection()
    clauses: list[str] = []
    params: list = []

    if remote_first:
        clauses.append("remote_policy IN ('fully-remote', 'remote-first')")
    if tech:
        clauses.append("tech_stack LIKE ?")
        params.append(f"%{tech}%")

    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT name, website, remote_policy, tech_stack, source FROM companies {where} ORDER BY name LIMIT ?",
        params,
    ).fetchall()
    conn.close()

    if not rows:
        click.echo("No companies found.")
        return

    click.echo(f"Found {len(rows)} company/ies:\n")
    for r in rows:
        policy = f" [{r['remote_policy']}]" if r["remote_policy"] else ""
        click.echo(f"  {r['name']}{policy}")
        if r["website"]:
            click.echo(f"    {r['website']}")
        if r["tech_stack"]:
            click.echo(f"    Tech: {r['tech_stack']}")
        click.echo()


if __name__ == "__main__":
    cli()
