# Remote Job Scraper & Matcher -- Workflow Overview

## Purpose

Automated pipeline that scrapes ~850 remote-friendly companies' career pages, extracts raw job listing text, then scores and ranks openings against a personal profile (skills, role preferences, exclusions) to surface the best-fit opportunities.

---

## Pipeline Stages

### Stage 1: Parse Company URLs

- Shallow-clones the [remoteintech/remote-jobs](https://github.com/remoteintech/remote-jobs) GitHub repo
- Parses ~850 markdown company profiles to extract `careers_url` or `website`
- Output: list of `{company, careers_url}` objects

### Stage 2: Crawl Career Pages

- Launches headless Chromium via **Playwright** (async, 10 concurrent browser contexts)
- For each company:
  1. Navigates to the careers URL
  2. Runs heuristic link detection:
     - Keyword matching on anchor text (`see jobs`, `open positions`, etc.)
     - URL path pattern matching (`/jobs`, `/careers/search`, etc.)
     - ATS iframe detection (Greenhouse, Lever, Workday, Ashby, Workable)
  3. Follows the best candidate link to reach the actual listings page

### Stage 3: Extract Raw Text

- Strips non-content elements (`<script>`, `<style>`, `<nav>`, `<footer>`)
- Captures full visible page text + all page links with URLs
- Flags pages with <200 chars as `insufficient_content`
- Writes each result as a JSON line to `data/scraped_roles.jsonl`

### Stage 4: Profile Matching & Ranking

- Loads a `profile.json` containing target roles, skills, and exclusion rules
- Scores each scraped page using a weighted system:
  - **Role title match** -- 5 pts (e.g. "Operations Analyst", "Trade Support")
  - **Operations/finance skills** -- 3 pts (e.g. "Reconciliation", "Settlement")
  - **Preferred keywords** -- 2 pts (e.g. "fintech", "Python", "Web3")
  - **Technical skills** -- 2 pts (e.g. "Python", "Solidity", "Alteryx")
  - **Methodology match** -- 2 pts (e.g. "Agile", "Process Automation")
  - **Exclude penalty** -- -100 pts (e.g. "on-site required", "Java required")
- Extracts individual job posting links from top-scoring pages
- Outputs ranked results to `data/matched_roles.json`

---

## Architecture

```
remoteintech/remote-jobs repo
         |
         v
  [Stage 1: Parse]  ──>  Company list (850+)
         |
         v
  [Stage 2: Crawl]  ──>  Headless Chromium x10 concurrency
         |                     |
         |           Heuristic link finder
         |           ATS embed detection
         v
  [Stage 3: Extract] ──>  scraped_roles.jsonl
         |
         v
  [Stage 4: Match]  ──>  Profile scoring engine
         |
         v
    matched_roles.json  (ranked opportunities)
```

---

## Tech Stack

| Component       | Technology                        |
|-----------------|-----------------------------------|
| Language        | Python 3.11+                      |
| Browser engine  | Playwright (async, headless Chromium) |
| Concurrency     | asyncio + semaphore (10 contexts) |
| Data format     | JSONL (scrape) / JSON (matches)   |
| Source repo     | GitPython / subprocess            |
| Infra           | Local only -- no Docker, no APIs  |

---

## Key Numbers

| Metric             | Value           |
|--------------------|-----------------|
| Companies scraped  | ~850            |
| Concurrency        | 10 browsers     |
| Timeout per site   | 30s             |
| Total runtime      | < 30 minutes    |
| Scoring categories | 5 weighted tiers|

---

## Output Files

- `data/scraped_roles.jsonl` -- one JSON record per company (text, URLs, errors)
- `data/matched_roles.json` -- scored and ranked matches against profile
- `data/matched_roles.md` -- human-readable report of top matches
