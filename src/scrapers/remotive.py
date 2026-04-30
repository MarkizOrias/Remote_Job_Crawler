"""Remotive scraper — JSON API at https://remotive.com/api/remote-jobs."""

import logging
import re

from src.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

SALARY_RE = re.compile(r"\$?([\d,.]+)\s*[kK]?\s*[-–]\s*\$?([\d,.]+)\s*[kK]?")


class RemotiveScraper(BaseScraper):
    name = "remotive"
    base_url = "https://remotive.com"

    async def scrape(self) -> list[Job]:
        logger.info("[remotive] Fetching job listings from API...")
        data = await self._get_json(f"{self.base_url}/api/remote-jobs")

        if not isinstance(data, dict):
            logger.warning("[remotive] Unexpected API response type: %s", type(data))
            return []

        listings = data.get("jobs", [])
        jobs: list[Job] = []

        for entry in listings:
            try:
                job = self._parse_entry(entry)
                if job:
                    jobs.append(job)
            except Exception:
                logger.debug("[remotive] Failed to parse entry: %s", entry.get("id"), exc_info=True)

        logger.info("[remotive] Parsed %d jobs from %d listings", len(jobs), len(listings))
        return jobs

    def _parse_entry(self, entry: dict) -> Job | None:
        title = (entry.get("title") or "").strip()
        company = (entry.get("company_name") or "").strip()
        url = (entry.get("url") or "").strip()

        if not title or not company or not url:
            return None

        tags = entry.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        category = entry.get("category", "")
        if category and category not in tags:
            tags.append(category)

        salary_min, salary_max = self._parse_salary(entry.get("salary", ""))

        date_posted = entry.get("publication_date")
        if date_posted:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(date_posted)
                date_posted = dt.replace(tzinfo=timezone.utc).isoformat()
            except (ValueError, AttributeError):
                pass

        location = (entry.get("candidate_required_location") or "").strip() or "Remote"

        return Job(
            title=title,
            company=company,
            url=url,
            source=self.name,
            external_id=str(entry.get("id", "")),
            company_url=entry.get("company_logo"),
            description=entry.get("description", ""),
            location=location,
            salary_min=salary_min,
            salary_max=salary_max,
            tags=tags,
            job_type=entry.get("job_type"),
            date_posted=date_posted,
            raw_data=entry,
        )

    @staticmethod
    def _parse_salary(salary_str: str) -> tuple[int | None, int | None]:
        """Parse salary strings like '$60k - $90k' or '$60,000 - $90,000'."""
        if not salary_str:
            return None, None

        m = SALARY_RE.search(salary_str)
        if not m:
            return None, None

        lo_str = m.group(1).replace(",", "")
        hi_str = m.group(2).replace(",", "")

        try:
            lo = float(lo_str)
            hi = float(hi_str)
        except ValueError:
            return None, None

        is_k = "k" in salary_str.lower()
        if is_k or lo < 1000:
            lo *= 1000
            hi *= 1000

        return int(lo), int(hi)
