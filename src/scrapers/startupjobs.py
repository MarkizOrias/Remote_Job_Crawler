"""startup.jobs scraper — Playwright-based with Cloudflare fallback.

Site uses Cloudflare bot protection. Attempts Playwright rendering;
logs and returns empty on block.
"""

import logging
from urllib.parse import urljoin

from src.scrapers.base import BaseScraper, Job
from src.scrapers.browser import get_browser, get_page, safe_goto

logger = logging.getLogger(__name__)


class StartupJobsScraper(BaseScraper):
    name = "startupjobs"
    base_url = "https://startup.jobs"

    async def scrape(self) -> list[Job]:
        logger.info("[startupjobs] Scraping via Playwright...")

        async with get_browser() as browser:
            async with get_page(browser, timeout=30000) as page:
                if not await safe_goto(page, f"{self.base_url}/?remote=true"):
                    return []

                await page.wait_for_timeout(5000)

                html = await page.content()
                if "challenge" in html.lower() or "captcha" in html.lower():
                    logger.warning("[startupjobs] Blocked by Cloudflare bot protection — skipping")
                    return []

                # Paginate through results
                all_jobs: list[Job] = []
                page_num = 1

                while page_num <= 5:
                    jobs = await self._extract_page(page)
                    if not jobs:
                        break
                    all_jobs.extend(jobs)
                    logger.debug("[startupjobs] Page %d: %d jobs", page_num, len(jobs))

                    next_btn = await page.query_selector("a[rel='next'], [class*='next'] a, a:has-text('Next')")
                    if not next_btn:
                        break
                    await next_btn.click()
                    await page.wait_for_timeout(3000)
                    page_num += 1

                logger.info("[startupjobs] Parsed %d jobs total", len(all_jobs))
                return all_jobs

    async def _extract_page(self, page) -> list[Job]:
        cards = await page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="/jobs/"]');
            for (const a of links) {
                const href = a.getAttribute('href');
                if (!href || href === '/jobs' || href === '/jobs/') continue;
                const card = a.closest('.job-card, .job-listing, article, div') || a;
                const titleEl = card.querySelector('h2, h3, .title, .job-title') || a;
                const companyEl = card.querySelector('.company, .company-name, .employer');
                const locationEl = card.querySelector('.location, .job-location');
                results.push({
                    href,
                    title: titleEl.innerText.trim().substring(0, 200),
                    company: companyEl ? companyEl.innerText.trim() : '',
                    location: locationEl ? locationEl.innerText.trim() : '',
                });
            }
            return results;
        }""")

        jobs: list[Job] = []
        seen: set[str] = set()
        for card in cards:
            href = card.get("href", "")
            title = card.get("title", "").strip()
            if not href or not title or href in seen:
                continue
            seen.add(href)

            full_url = urljoin(self.base_url, href)
            jobs.append(Job(
                title=title,
                company=card.get("company", "").strip() or "Unknown",
                url=full_url,
                source=self.name,
                external_id=href,
                location=card.get("location", "").strip() or "Remote",
            ))

        return jobs
