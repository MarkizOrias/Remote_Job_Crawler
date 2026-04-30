# CLAUDE.md — Remote Startup Job Scraper

## Project Overview

Build a **production-grade Python job scraper** that collects remote startup job listings from multiple sources into a unified SQLite database with a CLI interface and optional web dashboard. The scraper should run autonomously on a schedule and deduplicate listings across sources.

---

## Target Sources

### Tier 1 — Structured / API-friendly

| Source                | Method             | URL                                    |
| --------------------- | ------------------ | -------------------------------------- |
| RemoteOK              | JSON API           | `https://remoteok.com/api`             |
| Wellfound (AngelList) | Playwright scraper | `https://wellfound.com/role/remote`    |
| startup.jobs          | Scraper            | `https://startup.jobs/?remote=true`    |
| Remotive              | JSON API           | `https://remotive.com/api/remote-jobs` |

### Tier 2 — GitHub company directories (scrape → enrich)

| Source                                | Method                        | URL                                                        |
| ------------------------------------- | ----------------------------- | ---------------------------------------------------------- |
| remoteintech                          | Parse markdown/JSON from repo | `https://github.com/remoteintech/remote-jobs`              |
| yanirs/established-remote             | Parse markdown from repo      | `https://github.com/yanirs/established-remote`             |
| fireball787b/awesome-remote-companies | Parse markdown from repo      | `https://github.com/fireball787b/awesome-remote-companies` |

### Tier 3 — Board scrapers

| Source            | Method  | URL                            |
| ----------------- | ------- | ------------------------------ |
| We Work Remotely  | Scraper | `https://weworkremotely.com/`  |
| Remote First Jobs | Scraper | `https://remotefirstjobs.com/` |
| TrueUp            | Scraper | `https://www.trueup.io/remote` |
| DayOneJobs        | Scraper | `https://dayonejobs.com/`      |

---

## Architecture

```
remote-job-scraper/
├── claude.md                  # This file
├── pyproject.toml             # Project config (use uv or pip)
├── README.md                  # Setup & usage docs
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI entrypoint (click or argparse)
│   ├── config.py              # Settings, DB path, rate limits, user-agent
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLite schema via SQLAlchemy or raw SQL
│   │   ├── connection.py      # DB connection + migrations
│   │   └── queries.py         # Common queries (search, filter, stats)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract BaseScraper class
│   │   ├── remoteok.py
│   │   ├── wellfound.py
│   │   ├── startupjobs.py
│   │   ├── remotive.py
│   │   ├── weworkremotely.py
│   │   ├── remotefirstjobs.py
│   │   ├── trueup.py
│   │   ├── dayonejobs.py
│   │   └── github_lists.py    # Handles all 3 GitHub repos
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── deduplication.py   # Fuzzy matching on title+company
│   │   ├── normalizer.py      # Normalize titles, tags, locations
│   │   └── company_resolver.py # Match GitHub list companies → job postings
│   ├── export/
│   │   ├── __init__.py
│   │   ├── csv_export.py
│   │   ├── json_export.py
│   │   └── markdown_export.py
│   └── scheduler.py           # APScheduler or cron-like scheduling
├── dashboard/                 # Optional: simple web UI
│   ├── app.py                 # Flask/FastAPI app
│   ├── templates/
│   │   └── index.html
│   └── static/
├── tests/
│   ├── test_scrapers.py
│   ├── test_deduplication.py
│   └── test_normalizer.py
└── data/
    └── jobs.db                # SQLite database (gitignored)
```

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,              -- ID from source platform
    source TEXT NOT NULL,          -- 'remoteok', 'wellfound', etc.
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    company_url TEXT,
    description TEXT,
    url TEXT NOT NULL,             -- Direct link to listing
    location TEXT,                 -- 'Remote', 'Remote (EU)', 'Worldwide', etc.
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    tags TEXT,                     -- JSON array of tags/skills
    job_type TEXT,                 -- 'full-time', 'contract', 'part-time'
    experience_level TEXT,         -- 'junior', 'mid', 'senior', 'lead'
    date_posted TEXT,              -- ISO 8601
    date_scraped TEXT NOT NULL,    -- ISO 8601
    is_active INTEGER DEFAULT 1,
    dedup_hash TEXT,               -- For deduplication
    raw_data TEXT,                 -- Full JSON of original listing
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT,
    careers_url TEXT,
    description TEXT,
    size TEXT,                     -- '1-10', '11-50', '51-200', etc.
    remote_policy TEXT,            -- 'fully-remote', 'remote-first', 'hybrid'
    tech_stack TEXT,               -- JSON array
    source TEXT,                   -- Which GitHub list it came from
    glassdoor_rating REAL,
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    jobs_found INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
    error_message TEXT
);

CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_company ON jobs(company);
CREATE INDEX idx_jobs_tags ON jobs(tags);
CREATE INDEX idx_jobs_date_posted ON jobs(date_posted);
CREATE INDEX idx_jobs_dedup_hash ON jobs(dedup_hash);
```

---

## Implementation Rules

### General

- **Python 3.11+**
- Use `httpx` for async HTTP requests (not `requests`)
- Use `playwright` for JavaScript-rendered pages (Wellfound, TrueUp)
- Use `beautifulsoup4` + `lxml` for HTML parsing
- Use `sqlite3` directly (no ORM overhead) — but structure queries cleanly in `queries.py`
- All scrapers must inherit from `BaseScraper` and implement `scrape() -> list[Job]`
- Respect rate limits: **minimum 2 second delay** between requests to the same domain
- Rotate user-agents from a predefined list
- Log everything with `logging` module (INFO for runs, DEBUG for individual fetches)

### BaseScraper Interface

```python
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime

@dataclass
class Job:
    title: str
    company: str
    url: str
    source: str
    external_id: str | None = None
    company_url: str | None = None
    description: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    tags: list[str] = field(default_factory=list)
    job_type: str | None = None
    experience_level: str | None = None
    date_posted: str | None = None
    raw_data: dict | None = None

class BaseScraper(ABC):
    name: str  # e.g. 'remoteok'
    base_url: str

    @abstractmethod
    async def scrape(self) -> list[Job]:
        """Fetch and parse all available remote job listings."""
        ...

    async def _get(self, url: str) -> str:
        """Rate-limited HTTP GET with retries."""
        ...
```

### Deduplication Strategy

Generate a `dedup_hash` for each job using:

```python
import hashlib

def make_dedup_hash(title: str, company: str) -> str:
    normalized = f"{title.lower().strip()}|{company.lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

Before inserting, check if a job with the same `dedup_hash` already exists. If it does, update `date_scraped` and `is_active` but don't create a duplicate. Use fuzzy matching (`thefuzz` library) as a secondary check for near-duplicates with a threshold of 85%.

### GitHub List Parsing

For the GitHub company directories:

1. Fetch the raw markdown files from each repo
2. Parse company entries (name, website, remote policy, tech stack, region)
3. Store in the `companies` table
4. Cross-reference: when a job is scraped from Tier 1/3 sources, check if the company exists in the `companies` table and link them
5. **Bonus**: for companies in the GitHub lists that have a `careers_url`, periodically fetch that page and look for new job links

### CLI Interface

```bash
# Run all scrapers
python -m src.main scrape --all

# Run specific scraper
python -m src.main scrape --source remoteok
python -m src.main scrape --source wellfound

# Search jobs
python -m src.main search "data engineer" --remote-only --eu
python -m src.main search "python" --salary-min 80000

# List companies from GitHub directories
python -m src.main companies --remote-first --tech python

# Export results
python -m src.main export --format csv --output jobs.csv
python -m src.main export --format json --query "software engineer"
python -m src.main export --format markdown --last 7d

# Stats
python -m src.main stats
# Output: total jobs, by source, new today, top companies, top tags

# Mark stale listings
python -m src.main cleanup --older-than 30d
```

### Scraper-Specific Notes

| Scraper               | Notes                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **RemoteOK**          | JSON API at `/api` — returns array, first element is metadata (skip it). Rate limit: be gentle, 1 req/5s.                   |
| **Remotive**          | Clean JSON API. Paginated. Parse `tags`, `salary`, `job_type` directly.                                                     |
| **Wellfound**         | Requires Playwright. Login not needed for browsing. Paginate through listings. Extract company stage, funding, equity info. |
| **startup.jobs**      | HTML scraper. Filter URL param `?remote=true`. Paginate via `?page=N`.                                                      |
| **We Work Remotely**  | HTML scraper. Categories at `/remote-jobs/`. Parse each category page.                                                      |
| **TrueUp**            | May need Playwright. Dynamic loading. Parse job cards from DOM.                                                             |
| **DayOneJobs**        | HTML scraper. Check if API exists first.                                                                                    |
| **Remote First Jobs** | HTML scraper. May have anti-bot measures — use Playwright if needed.                                                        |
| **GitHub lists**      | Raw markdown via `https://raw.githubusercontent.com/...`. Parse with regex or markdown parser.                              |

### Error Handling

- Wrap each scraper in try/except — one failing source must not block others
- Retry failed HTTP requests up to 3 times with exponential backoff
- Log failures to `scrape_runs` table with error messages
- If a source consistently fails, skip it and warn in the summary

### Configuration (`config.py`)

```python
from pathlib import Path

DB_PATH = Path("data/jobs.db")
REQUEST_DELAY = 2.0  # seconds between requests to same domain
MAX_RETRIES = 3
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...",
    # Add 5-10 realistic user agents
]
LOG_LEVEL = "INFO"
LOG_FILE = Path("data/scraper.log")

# Source-specific overrides
SCRAPER_CONFIG = {
    "remoteok": {"delay": 5.0, "enabled": True},
    "wellfound": {"delay": 3.0, "enabled": True, "use_playwright": True},
    "remotive": {"delay": 2.0, "enabled": True},
    "startupjobs": {"delay": 2.0, "enabled": True},
    "weworkremotely": {"delay": 2.0, "enabled": True},
    "trueup": {"delay": 3.0, "enabled": True, "use_playwright": True},
    "dayonejobs": {"delay": 2.0, "enabled": True},
    "remotefirstjobs": {"delay": 3.0, "enabled": True},
    "github_lists": {"delay": 1.0, "enabled": True},
}
```

---

## Build Order

Follow this sequence strictly:

1. **Database layer** — schema, connection, migrations, basic queries
2. **BaseScraper + Job dataclass** — abstract interface and data model
3. **RemoteOK scraper** — simplest (JSON API), use to validate full pipeline
4. **Remotive scraper** — second JSON API source
5. **Deduplication + normalizer** — get this right before adding more sources
6. **CLI with `click`** — `scrape`, `search`, `export`, `stats` commands
7. **HTML scrapers** — startup.jobs, We Work Remotely, DayOneJobs
8. **Playwright scrapers** — Wellfound, TrueUp, Remote First Jobs
9. **GitHub list parser** — parse markdown, populate companies table
10. **Company cross-referencing** — link GitHub companies to scraped jobs
11. **Export module** — CSV, JSON, Markdown outputs
12. **Scheduler** — APScheduler for periodic runs
13. **Dashboard** (optional) — Flask app with search/filter UI
14. **Tests** — unit tests for parsers, dedup logic, normalizer

---

## Quality Checklist

Before considering any component complete:

- [ ] All scrapers return valid `Job` objects with required fields populated
- [ ] Deduplication correctly identifies same job posted on multiple boards
- [ ] Rate limiting is enforced per-domain
- [ ] Failed scrapers don't crash the entire run
- [ ] CLI search returns results within 100ms for 10k+ jobs
- [ ] Exports produce valid, well-formatted files
- [ ] Logs capture enough detail to debug scraper failures
- [ ] `scrape_runs` table tracks every run with accurate stats
- [ ] Schema migrations work on fresh DB and existing DB
- [ ] No hardcoded secrets or API keys in source code

---

## Dependencies

```
httpx
beautifulsoup4
lxml
playwright
click
thefuzz
python-Levenshtein
apscheduler
```

Install Playwright browsers after setup:

```bash
playwright install chromium
```

---

## User Context

The operator of this scraper is a **data/software engineer based in Switzerland**, pivoting from banking operations into IT. Primary interest is in:

- Remote positions open to **EU / Switzerland / Worldwide**
- Roles: **data engineer, software engineer, Python developer, backend engineer**
- Companies: startups and scale-ups, especially in **fintech, Web3/DeFi, and dev tools**

The search and filter features should make it easy to narrow down to these criteria.
