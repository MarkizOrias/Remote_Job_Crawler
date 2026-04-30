"""SQLite schema definitions."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    company_url TEXT,
    description TEXT,
    url TEXT NOT NULL,
    location TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    tags TEXT,
    job_type TEXT,
    experience_level TEXT,
    date_posted TEXT,
    date_scraped TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    dedup_hash TEXT,
    raw_data TEXT,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT,
    careers_url TEXT,
    description TEXT,
    size TEXT,
    remote_policy TEXT,
    tech_stack TEXT,
    source TEXT,
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
    status TEXT DEFAULT 'running',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_tags ON jobs(tags);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_jobs_dedup_hash ON jobs(dedup_hash);
"""
