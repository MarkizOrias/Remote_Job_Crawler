"""DayOneJobs scraper — Playwright-based (Next.js, client-rendered)."""

import logging
import re
from urllib.parse import urljoin

from src.scrapers.base import BaseScraper, Job
from src.scrapers.browser import get_browser, get_page, safe_goto

logger = logging.getLogger(__name__)

SALARY_RE = re.compile(r"\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)")


class DayOneJobsScraper(BaseScraper):
    name = "dayonejobs"
    base_url = "https://www.dayonejobs.com"

    async def scrape(self) -> list[Job]:
        logger.info("[dayonejobs] Scraping via Playwright...")

        async with get_browser() as browser:
            async with get_page(browser, timeout=30000) as page:
                if not await safe_goto(page, f"{self.base_url}/jobs"):
                    return []

                await page.wait_for_timeout(5000)

                title = await page.title()
                if "just a moment" in title.lower():
                    logger.warning("[dayonejobs] Blocked by Cloudflare — skipping")
                    return []

                # Scroll to trigger lazy loading
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)

                cards = await page.evaluate("""() => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/jobs/"]');
                    for (const a of links) {
                        const href = a.getAttribute('href');
                        if (!href || href === '/jobs' || href === '/jobs/') continue;

                        const container = a.closest('div')?.parentElement || a.closest('div') || a;
                        const text = container.innerText || '';
                        results.push({ href, text: text.substring(0, 600) });
                    }
                    return results;
                }""")

                jobs = self._parse_cards(cards)
                logger.info("[dayonejobs] Parsed %d jobs", len(jobs))
                return jobs

    def _parse_cards(self, cards: list[dict]) -> list[Job]:
        jobs: list[Job] = []
        seen: set[str] = set()

        for card in cards:
            href = card.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)

            text = card.get("text", "")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not lines:
                continue

            title = lines[0]
            company = lines[1] if len(lines) > 1 else "Unknown"

            # Skip nav-like text
            if len(title) < 4 or title.lower() in ("view job post", "jobs"):
                continue

            location = self._extract_field(lines, "Location")
            job_type = self._extract_field(lines, "Employment Type")
            salary_str = self._extract_field(lines, "Salary")
            salary_min, salary_max = self._parse_salary(salary_str)

            full_url = urljoin(self.base_url, href)

            jobs.append(Job(
                title=title,
                company=company,
                url=full_url,
                source=self.name,
                external_id=href,
                location=location or "Unknown",
                job_type=job_type,
                salary_min=salary_min,
                salary_max=salary_max,
            ))

        return jobs

    @staticmethod
    def _extract_field(lines: list[str], label: str) -> str | None:
        for i, line in enumerate(lines):
            if line.lower() == label.lower() and i + 1 < len(lines):
                return lines[i + 1]
        return None

    @staticmethod
    def _parse_salary(salary_str: str | None) -> tuple[int | None, int | None]:
        if not salary_str:
            return None, None
        m = SALARY_RE.search(salary_str)
        if not m:
            return None, None
        try:
            lo = int(m.group(1).replace(",", ""))
            hi = int(m.group(2).replace(",", ""))
            return lo, hi
        except ValueError:
            return None, None
