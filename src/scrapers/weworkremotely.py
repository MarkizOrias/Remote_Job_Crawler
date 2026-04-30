"""We Work Remotely scraper — HTML scraper across category pages."""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

CATEGORIES = [
    "/categories/remote-back-end-programming-jobs",
    "/categories/remote-front-end-programming-jobs",
    "/categories/remote-full-stack-programming-jobs",
    "/categories/remote-design-jobs",
    "/categories/remote-customer-support-jobs",
    "/categories/remote-devops-sysadmin-jobs",
    "/categories/remote-finance-legal-jobs",
    "/categories/remote-product-jobs",
    "/categories/remote-data-jobs",
    "/categories/all-other-remote-jobs",
]


class WeWorkRemotelyScraper(BaseScraper):
    name = "weworkremotely"
    base_url = "https://weworkremotely.com"

    async def scrape(self) -> list[Job]:
        logger.info("[wwr] Scraping %d category pages...", len(CATEGORIES))
        seen_hrefs: set[str] = set()
        jobs: list[Job] = []

        for cat_path in CATEGORIES:
            url = f"{self.base_url}{cat_path}"
            try:
                html = await self._get(url)
                page_jobs = self._parse_category(html, cat_path)
                for job in page_jobs:
                    if job.url not in seen_hrefs:
                        seen_hrefs.add(job.url)
                        jobs.append(job)
            except Exception:
                logger.warning("[wwr] Failed to scrape %s", cat_path, exc_info=True)

        logger.info("[wwr] Parsed %d unique jobs across %d categories", len(jobs), len(CATEGORIES))
        return jobs

    def _parse_category(self, html: str, cat_path: str) -> list[Job]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("section.jobs article ul li")
        jobs: list[Job] = []

        category = cat_path.split("/")[-1].replace("remote-", "").replace("-jobs", "").replace("-", " ").title()

        for li in items:
            link = li.select_one("a.listing-link--unlocked, a.listing-link--locked")
            if not link:
                continue

            href = link.get("href", "")
            if not href or href.startswith("javascript"):
                continue

            title_el = link.select_one(".new-listing__header__title__text")
            company_el = link.select_one(".new-listing__company-name")

            title = title_el.get_text(strip=True) if title_el else None
            company = company_el.get_text(strip=True) if company_el else None

            if not title or not company:
                continue

            location_el = link.select_one(".new-listing__company-headquarters")
            location = location_el.get_text(strip=True) if location_el else ""

            cat_spans = link.select(".new-listing__categories__category")
            tags: list[str] = []
            job_type: str | None = None
            for span in cat_spans:
                text = span.get_text(strip=True)
                lower = text.lower()
                if lower in ("featured",):
                    continue
                if lower in ("full-time", "part-time", "contract", "freelance"):
                    job_type = lower
                else:
                    tags.append(text)

            if not location:
                for tag in tags:
                    if "anywhere" in tag.lower() or "world" in tag.lower():
                        location = tag
                        break

            if category:
                tags.append(category)

            full_url = urljoin(self.base_url, href)

            jobs.append(Job(
                title=title,
                company=company,
                url=full_url,
                source=self.name,
                external_id=href,
                location=location or "Remote",
                tags=tags,
                job_type=job_type,
            ))

        return jobs
