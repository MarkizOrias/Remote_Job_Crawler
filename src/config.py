"""Settings, DB path, rate limits, user-agent rotation."""

import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "jobs.db"
LOG_FILE = BASE_DIR / "data" / "scraper.log"
LOG_LEVEL = logging.INFO

REQUEST_DELAY = 2.0
MAX_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

SCRAPER_CONFIG: dict[str, dict] = {
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


def setup_logging() -> None:
    """Configure root logger for the scraper."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
