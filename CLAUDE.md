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

---

## Iterative Self-Improvement Loop (MANDATORY)

After the initial scrape completes, you are NOT done. Your job is to continuously improve the success rate until you've exhausted every reasonable avenue. Follow this loop:

### Step 1: Analyze Failures

After each run, immediately analyze `data/scraped_roles.jsonl`:

- Count successes (non-null `text` with >200 chars) vs failures (null `text` or `error` set)
- Categorize failures into buckets: `timeout`, `insufficient_content`, `navigation_error`, `connection_refused`, `captcha/login_wall`, `empty_page`, `redirect_loop`, other
- Print a breakdown: `Success: 612/835 (73%) | Timeout: 89 | Empty: 54 | Nav error: 41 | Other: 39`
- Write the failure analysis to `data/failure_report.md`

### Step 2: Diagnose Patterns

Look at the actual failed URLs and error messages. Ask yourself:

- Are many failures from the same ATS provider I'm not handling? (e.g., `smartrecruiters.com`, `jobvite.com`, `ashbyhq.com`, `breezy.hr`, `workable.com`) → **Add detection for that ATS**
- Are timeouts happening because `networkidle` is too strict? → **Switch to `domcontentloaded` + a fixed wait for those domains**
- Are pages loading but returning minimal text because content is inside a shadow DOM or React root that hasn't hydrated? → **Add `page.wait_for_selector()` for common job card selectors before extracting text**
- Are redirects landing on a generic homepage instead of careers? → **Improve the heuristic link finder with new keyword patterns observed in the failures**
- Are some sites blocking headless Chrome? → **Adjust browser fingerprint: locale, viewport, webdriver flag**

### Step 3: Fix and Re-Run Failures Only

- Do NOT re-scrape companies that already succeeded
- Filter the company list to only those with errors or insufficient content
- Apply your fixes to the heuristics/crawl logic
- Re-run the pipeline on the filtered list
- Merge new results into the existing JSONL (overwrite entries for re-scraped companies)

### Step 4: Repeat Until Plateau

- After each improvement cycle, compare the new success rate to the previous one
- Print: `Cycle 3: 743/835 (89%) — +31 recovered this cycle`
- Keep looping as long as each cycle recovers at least 5 new companies
- When a cycle recovers fewer than 5, you've plateaued — stop and produce the final report

### What Counts as "Done"

You are done when ALL of the following are true:

1. You have run **at least 3 improvement cycles** after the initial scrape
2. The last cycle recovered **fewer than 5 companies**
3. You have produced `data/final_report.md` containing:
   - Total success rate and count
   - Success rate per improvement cycle (table)
   - List of all remaining failures with their error category and URL
   - A summary of every heuristic/fix you added across cycles
   - Honest assessment of what's left unfixable (e.g., companies that shut down, pure CAPTCHA walls)

### Rules for the Improvement Loop

- **Never stop after the first run.** The first run is a baseline, not the deliverable.
- **Never say "good enough."** If there are fixable failures, fix them.
- **Never repeat the same fix twice.** Each cycle must try something new.
- **Log every change you make** between cycles so you can explain what worked.
- **Keep the codebase under 700 lines total** even after improvements — refactor as you go, don't just bolt on hacks.
- **Each cycle should complete in under 15 minutes** since you're only re-scraping failures.
- **If you're stuck on a category of failures**, sample 3-5 URLs from that category, manually inspect what the page looks like (take a screenshot via Playwright if needed), and adapt your heuristics based on what you actually see.
