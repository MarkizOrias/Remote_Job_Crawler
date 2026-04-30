"""RemoteOK scraper — JSON API at https://remoteok.com/api."""

import logging
from datetime import datetime, timezone

from src.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)


class RemoteOKScraper(BaseScraper):
    name = "remoteok"
    base_url = "https://remoteok.com"

    async def scrape(self) -> list[Job]:
        logger.info("[remoteok] Fetching job listings from API...")
        data = await self._get_json(f"{self.base_url}/api")

        if not isinstance(data, list) or len(data) < 2:
            logger.warning("[remoteok] Unexpected API response shape")
            return []

        # First element is metadata — skip it
        listings = data[1:]
        jobs: list[Job] = []

        for entry in listings:
            try:
                job = self._parse_entry(entry)
                if job:
                    jobs.append(job)
            except Exception:
                logger.debug("[remoteok] Failed to parse entry: %s", entry.get("id"), exc_info=True)

        logger.info("[remoteok] Parsed %d jobs from %d listings", len(jobs), len(listings))
        return jobs

    def _parse_entry(self, entry: dict) -> Job | None:
        title = entry.get("position", "").strip()
        company = entry.get("company", "").strip()
        url = entry.get("url", "")

        if not title or not company:
            return None

        if url and not url.startswith("http"):
            url = f"{self.base_url}{url}"

        tags = entry.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        salary_min = self._parse_salary(entry.get("salary_min"))
        salary_max = self._parse_salary(entry.get("salary_max"))

        date_posted = entry.get("date")
        if date_posted:
            try:
                dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                date_posted = dt.isoformat()
            except (ValueError, AttributeError):
                pass

        location = entry.get("location", "").strip() or "Remote"

        return Job(
            title=title,
            company=company,
            url=url,
            source=self.name,
            external_id=str(entry.get("id", "")),
            company_url=entry.get("company_logo", None),
            description=entry.get("description", ""),
            location=location,
            salary_min=salary_min,
            salary_max=salary_max,
            tags=tags,
            date_posted=date_posted,
            raw_data=entry,
        )

    @staticmethod
    def _parse_salary(val) -> int | None:
        if val is None:
            return None
        try:
            return int(str(val).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None
