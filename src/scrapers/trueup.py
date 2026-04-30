"""TrueUp scraper — Playwright-based.

Currently blocked by Cloudflare bot protection in headless mode.
Logs the limitation and returns empty results gracefully.
"""

import logging

from src.scrapers.base import BaseScraper, Job
from src.scrapers.browser import get_browser, get_page, safe_goto

logger = logging.getLogger(__name__)


class TrueUpScraper(BaseScraper):
    name = "trueup"
    base_url = "https://www.trueup.io"

    async def scrape(self) -> list[Job]:
        logger.info("[trueup] Attempting to scrape via Playwright...")

        async with get_browser() as browser:
            async with get_page(browser) as page:
                if not await safe_goto(page, f"{self.base_url}/remote"):
                    return []

                await page.wait_for_timeout(5000)
                title = await page.title()

                if "just a moment" in title.lower() or "challenge" in (await page.content()).lower():
                    logger.warning("[trueup] Blocked by Cloudflare bot protection — skipping")
                    return []

                jobs = await self._extract_jobs(page)
                logger.info("[trueup] Parsed %d jobs", len(jobs))
                return jobs

    async def _extract_jobs(self, page) -> list[Job]:
        cards = await page.eval_on_selector_all(
            "a[href*='/job/']",
            """els => els.map(el => {
                return {
                    title: el.innerText.trim().substring(0, 200),
                    url: el.getAttribute('href') || '',
                };
            })""",
        )

        jobs: list[Job] = []
        for card in cards:
            title = card.get("title", "").strip()
            url = card.get("url", "").strip()
            if not title or len(title) < 5:
                continue
            if url and not url.startswith("http"):
                url = f"{self.base_url}{url}"

            parts = title.split("\n")
            job_title = parts[0].strip()
            company = parts[1].strip() if len(parts) > 1 else "Unknown"

            jobs.append(Job(
                title=job_title,
                company=company,
                url=url or self.base_url,
                source=self.name,
                location="Remote",
            ))

        return jobs
