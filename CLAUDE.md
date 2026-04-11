# Job Scraper Pipeline

## Code Quality

- Use claude-opus-4-6 for all tasks
- Write production-grade Python: full type hints, docstrings, proper error handling
- Use async/await throughout — no sync blocking calls
- Use dataclasses or Pydantic models for all data structures
- Add logging (structlog or stdlib logging) — no bare print() calls except for progress display
- Follow PEP 8, use pathlib over os.path, f-strings over .format()

## Goal

Scrape ~835 companies' career pages from the [remote-jobs](https://github.com/remoteintech/remote-jobs) repo, extract all open role listings with descriptions, and dump everything to a single JSONL file for downstream analysis.

## Pipeline Overview

Three stages, run sequentially:

1. **Parse company URLs** from the GitHub repo
2. **Crawl career pages** and follow "view jobs" links to reach actual listings
3. **Extract role data** (title, description, location, URL) from listings pages

## Stage 1: Parse GitHub Repo

- Clone or fetch `https://github.com/remoteintech/remote-jobs` (shallow clone is fine)
- Each company has a markdown file under `src/companies/`
- Each file contains a `website` field (URL) — extract it
- Some files have a dedicated `careers_url` or the website itself is the careers page — check for both
- Output: a list of `{company_name, careers_url}` objects

## Stage 2: Crawl Career Pages → Find Listings

This is the hardest part. Each company's careers page is different. Use **Playwright async** (headed=false) with a pool of ~10 browser contexts and a semaphore for concurrency.

For each `careers_url`:

1. Navigate to the page (`wait_until='networkidle'`, timeout 15s)
2. Run a **heuristic link finder** to locate the "see jobs" / "open positions" link or button:
   - Scan all `<a>` tags: match inner text against keywords like `see|view|browse|search|explore|find|open` + `jobs|positions|roles|openings|opportunities` (case-insensitive)
   - Scan `<button>` tags with the same keyword regex — if matched, click it and wait for navigation
   - Fallback: scan all `href` attributes for path patterns like `/jobs`, `/positions`, `/openings`, `/careers/search`, `/careers/listings`
   - Detect common ATS embeds: if the page contains an `<iframe>` whose `src` matches `boards.greenhouse.io`, `jobs.lever.co`, `*.myworkdayjobs.com`, extract that iframe URL and navigate to it directly
3. If a jobs link is found, navigate to it (resolve relative URLs against current page origin)
4. Once on the listings page, scrape it (Stage 3)
5. If nothing is found, scrape the current page as-is — it may already be the listings page

**Resilience rules:**

- Timeout per company: 30s total (navigation + finding link + scraping)
- On any error, log it and move on — never block the pipeline
- Respect a 1s delay between navigations to avoid aggressive rate-limiting
- Rotate a realistic User-Agent header

## Stage 3: Extract Role Data

On the final listings page, extract raw text content:

- Strip `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>` tags
- Get the remaining visible text via `page.inner_text('body')` or equivalent
- If the text is very short (<200 chars), the page likely requires JS interaction or is a dead link — log as `insufficient_content`
- Do NOT attempt to parse individual role cards into structured fields — just grab the full page text. The analysis step will handle extraction.

## Output Format

Write results to `data/scraped_roles.jsonl`, one JSON object per line:

```json
{
  "company": "Akamai",
  "careers_url": "https://www.akamai.com/careers",
  "final_url": "https://akamai.wd1.myworkdayjobs.com/search",
  "text": "... full visible text of the listings page ...",
  "scraped_at": "2026-04-09T12:00:00Z",
  "error": null
}
```

For failures:

```json
{
  "company": "SomeCompany",
  "careers_url": "https://example.com/careers",
  "final_url": null,
  "text": null,
  "scraped_at": "2026-04-09T12:00:05Z",
  "error": "timeout navigating to careers page"
}
```

## Tech Stack

- **Python 3.11+**
- **Playwright** (`pip install playwright && playwright install chromium`) — async API only
- **aiofiles** for async JSONL writing
- **GitPython** or just `subprocess` for cloning the repo
- No external scraping services, no APIs, no proxies — just local headless Chromium

## Project Structure

```
job-scraper/
├── scraper/
│   ├── __init__.py
│   ├── parse_repo.py      # Stage 1: parse markdown files → company list
│   ├── crawl.py            # Stage 2+3: Playwright crawl + extract
│   └── heuristics.py       # Link-finding heuristics, ATS detection
├── data/
│   └── scraped_roles.jsonl  # Output
├── main.py                  # Orchestrator: parse → crawl → write
├── requirements.txt
└── README.md
```

## Running

```bash
python main.py
```

Should complete all 835 companies in **under 30 minutes** with 10 concurrent browser contexts.

Print a progress line every 50 companies: `[150/835] 18% done — 3 errors so far`

## Important Constraints

- Do NOT over-engineer. No database, no queue system, no Docker. Just a script that runs.
- Do NOT try to parse roles into structured fields during scraping. The raw text dump is the deliverable.
- Do NOT spend time on retries for failed pages. Log the error, move on.
- If a site redirects to a login wall or CAPTCHA, log it as an error and skip.
- Keep the total codebase under 500 lines.
