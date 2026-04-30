"""Abstract BaseScraper and Job dataclass."""

import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from src.config import MAX_RETRIES, REQUEST_DELAY, SCRAPER_CONFIG, USER_AGENTS

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """Unified job listing record."""

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

    @property
    def dedup_hash(self) -> str:
        normalized = f"{self.title.lower().strip()}|{self.company.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def to_db_dict(self) -> dict:
        """Convert to a dict matching the database columns."""
        return {
            "external_id": self.external_id,
            "source": self.source,
            "title": self.title,
            "company": self.company,
            "company_url": self.company_url,
            "description": self.description,
            "url": self.url,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "tags": self.tags,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "date_posted": self.date_posted,
            "date_scraped": datetime.now(timezone.utc).isoformat(),
            "dedup_hash": self.dedup_hash,
            "raw_data": self.raw_data,
        }


class BaseScraper(ABC):
    """Abstract base for all scrapers."""

    name: str
    base_url: str

    def __init__(self) -> None:
        cfg = SCRAPER_CONFIG.get(self.name, {})
        self.delay: float = cfg.get("delay", REQUEST_DELAY)
        self.enabled: bool = cfg.get("enabled", True)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": random.choice(USER_AGENTS)},
                follow_redirects=True,
                timeout=30.0,
            )
        return self._client

    async def _get(self, url: str) -> str:
        """Rate-limited HTTP GET with retries."""
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await asyncio.sleep(self.delay)
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = self.delay * (2 ** attempt)
                logger.warning(
                    "[%s] GET %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    self.name, url, attempt, MAX_RETRIES, exc, wait,
                )
                await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]

    async def _get_json(self, url: str) -> dict | list:
        """Rate-limited HTTP GET returning parsed JSON."""
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await asyncio.sleep(self.delay)
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                wait = self.delay * (2 ** attempt)
                logger.warning(
                    "[%s] GET JSON %s failed (attempt %d/%d): %s",
                    self.name, url, attempt, MAX_RETRIES, exc,
                )
                await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]

    @abstractmethod
    async def scrape(self) -> list[Job]:
        """Fetch and parse all available remote job listings."""
        ...

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
