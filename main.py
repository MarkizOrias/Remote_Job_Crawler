"""Orchestrator: parse repo, crawl career pages, write JSONL."""

import asyncio
from pathlib import Path

from scraper.parse_repo import parse_companies
from scraper.crawl import crawl_all

OUTPUT_PATH = Path("data/scraped_roles.jsonl")
PROGRESS_INTERVAL = 50


def make_progress_cb(total: int):
    state = {"completed": 0, "errors": 0, "last_printed": 0}

    def cb(_idx: int, error):
        state["completed"] += 1
        if error:
            state["errors"] += 1
        n = state["completed"]
        if n - state["last_printed"] >= PROGRESS_INTERVAL or n == total:
            pct = int(n / total * 100)
            print(f"[{n}/{total}] {pct}% done - {state['errors']} errors so far")
            state["last_printed"] = n

    return cb


def main():
    print("Stage 1: Parsing company URLs from remote-jobs repo...")
    companies = parse_companies()
    total = len(companies)
    print(f"Found {total} companies.")

    print(f"Stage 2+3: Crawling career pages -> {OUTPUT_PATH}")
    progress_cb = make_progress_cb(total)

    asyncio.run(crawl_all(companies, OUTPUT_PATH, progress_cb=progress_cb))

    # Final count
    if OUTPUT_PATH.exists():
        lines = OUTPUT_PATH.read_text(encoding="utf-8").strip().splitlines()
        errors = sum(1 for l in lines if '"error": null' not in l)
        print(f"\nDone. {len(lines)} records written, {errors} with errors -> {OUTPUT_PATH}")
    else:
        print("Done (no output file found).")


if __name__ == "__main__":
    main()
