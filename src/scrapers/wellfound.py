"""Wellfound (AngelList) scraper — Playwright-based.

Currently blocked by Cloudflare bot protection in headless mode.
Logs the limitation and returns empty results gracefully.
"""

import logging

from src.scrapers.base import BaseScraper, Job
from src.scrapers.browser import get_browser, get_page, safe_goto

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    name = "wellfound"
    base_url = "https://wellfound.com"

    async def scrape(self) -> list[Job]:
        logger.info("[wellfound] Attempting to scrape via Playwright...")

        async with get_browser() as browser:
            async with get_page(browser) as page:
                if not await safe_goto(page, f"{self.base_url}/jobs"):
                    return []

                await page.wait_for_timeout(5000)
                html = await page.content()

                if "captcha" in html.lower() or "challenge" in html.lower():
                    logger.warning("[wellfound] Blocked by Cloudflare bot protection — skipping")
                    return []

                jobs = await self._extract_jobs(page)
                logger.info("[wellfound] Parsed %d jobs", len(jobs))
                return jobs

    async def _extract_jobs(self, page) -> list[Job]:
        cards = await page.eval_on_selector_all(
            "[class*='JobListing'], [class*='job-card'], [data-test*='job']",
            """els => els.map(el => {
                const titleEl = el.querySelector('a[href*="/jobs/"]') || el.querySelector('h2, h3');
                const companyEl = el.querySelector('[class*="company"], [class*="Company"]');
                const locationEl = el.querySelector('[class*="location"], [class*="Location"]');
                const link = el.querySelector('a[href*="/jobs/"]');
                return {
                    title: titleEl ? titleEl.innerText.trim() : '',
                    company: companyEl ? companyEl.innerText.trim() : '',
                    location: locationEl ? locationEl.innerText.trim() : '',
                    url: link ? link.getAttribute('href') : '',
                };
            })""",
        )

        jobs: list[Job] = []
        for card in cards:
            title = card.get("title", "").strip()
            company = card.get("company", "").strip()
            url = card.get("url", "").strip()
            if not title or not company:
                continue
            if url and not url.startswith("http"):
                url = f"{self.base_url}{url}"

            jobs.append(Job(
                title=title,
                company=company,
                url=url or self.base_url,
                source=self.name,
                location=card.get("location", "Remote") or "Remote",
            ))

        return jobs
