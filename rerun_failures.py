"""Re-scrape only failed entries from data/scraped_roles.json and merge results.

Usage: python rerun_failures.py [--cycle N]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from scraper.crawl import crawl_all
from scraper.analyze import categorize


OUTPUT_PATH = Path("data/scraped_roles.json")
PROGRESS_INTERVAL = 25


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_progress_cb(total: int, label: str):
    state = {"completed": 0, "errors": 0, "last_printed": 0}

    def cb(_idx: int, error):
        state["completed"] += 1
        if error:
            state["errors"] += 1
        n = state["completed"]
        if n - state["last_printed"] >= PROGRESS_INTERVAL or n == total:
            pct = int(n / total * 100) if total else 0
            print(f"[{label}] [{n}/{total}] {pct}% - {state['errors']} errors")
            state["last_printed"] = n

    return cb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1)
    parser.add_argument("--include-ok", action="store_true",
                        help="also re-scrape ok records (for debugging)")
    parser.add_argument("--only", type=str, default="",
                        help="comma-separated category filter (e.g. timeout_total,insufficient_content)")
    args = parser.parse_args()

    records = load(OUTPUT_PATH)
    by_company: dict[str, dict] = {r["company"]: r for r in records}

    filters = {c.strip() for c in args.only.split(",") if c.strip()}

    targets: list[dict] = []
    for r in records:
        if not r.get("error") and not args.include_ok:
            continue
        cat = categorize(r.get("error"))
        if filters and cat not in filters:
            continue
        targets.append({"company": r["company"], "careers_url": r["careers_url"]})

    total = len(targets)
    print(f"Cycle {args.cycle}: re-scraping {total} entries")
    if not total:
        print("Nothing to re-scrape.")
        return

    progress_cb = make_progress_cb(total, f"cycle{args.cycle}")
    new_results = asyncio.run(
        crawl_all(targets, OUTPUT_PATH.with_suffix(f".cycle{args.cycle}.json"), progress_cb=progress_cb)
    )

    # Merge: replace entries by company name.
    recovered = 0
    for nr in new_results:
        prev = by_company.get(nr["company"])
        was_error = prev is None or prev.get("error")
        if was_error and not nr.get("error"):
            recovered += 1
        by_company[nr["company"]] = nr

    merged = sorted(by_company.values(), key=lambda r: (r.get("company") or "").lower())
    OUTPUT_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    succ = sum(1 for r in merged if not r.get("error") and r.get("text"))
    pct = succ / len(merged) * 100 if merged else 0
    print(
        f"Cycle {args.cycle} done. Recovered {recovered}. "
        f"Total success: {succ}/{len(merged)} ({pct:.1f}%)"
    )


if __name__ == "__main__":
    main()
