"""Stage 2+3: Crawl career pages and extract raw listing text."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from playwright.async_api import async_playwright

from .heuristics import find_jobs_url

log = logging.getLogger(__name__)

CONCURRENCY = 10
NAV_TIMEOUT = 15_000
NETWORKIDLE_GRACE = 5_000  # extra wait for JS after DOM loads
DELAY_BETWEEN_NAV = 1.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STRIP_TAGS_JS = """
() => {
    if (!document.body) return '';
    const clone = document.body.cloneNode(true);
    for (const tag of ['script','style','nav','footer','header','noscript']) {
        clone.querySelectorAll(tag).forEach(el => el.remove());
    }
    return clone.innerText;
}
"""

EXTRACT_LINKS_JS = """
() => {
    const seen = new Set();
    const links = [];
    for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href;
        const text = a.innerText.trim().substring(0, 200);
        if (!href || href.startsWith('javascript') || href === '#' || seen.has(href)) continue;
        seen.add(href);
        links.push({href, text});
    }
    return links;
}
"""


async def _navigate(page, url: str):
    """Navigate with domcontentloaded, then briefly try networkidle."""
    await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    try:
        await page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_GRACE)
    except Exception:
        pass  # Best-effort; DOM is already loaded


async def scrape_company(page, company: str, careers_url: str) -> dict:
    scraped_at = datetime.now(timezone.utc).isoformat()
    try:
        try:
            await _navigate(page, careers_url)
        except Exception as e:
            return _error(company, careers_url, scraped_at, f"timeout navigating to careers page: {e}")

        await asyncio.sleep(DELAY_BETWEEN_NAV)

        try:
            jobs_url = await find_jobs_url(page, page.url)
        except Exception:
            jobs_url = None

        final_url = page.url

        if jobs_url and jobs_url != page.url:
            try:
                await _navigate(page, jobs_url)
                final_url = page.url
                await asyncio.sleep(DELAY_BETWEEN_NAV)
            except Exception:
                pass

        try:
            text = await page.evaluate(STRIP_TAGS_JS)
        except Exception as e:
            return _error(company, careers_url, scraped_at, f"text extraction failed: {e}", final_url)

        # Extract all links from the page
        try:
            links = await page.evaluate(EXTRACT_LINKS_JS)
        except Exception:
            links = []

        if not text or len(text.strip()) < 200:
            return _error(company, careers_url, scraped_at, "insufficient_content", final_url)

        return {
            "company": company,
            "careers_url": careers_url,
            "final_url": final_url,
            "links": links,
            "text": text.strip(),
            "scraped_at": scraped_at,
            "error": None,
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _error(company, careers_url, scraped_at, msg, final_url=None):
    return {
        "company": company,
        "careers_url": careers_url,
        "final_url": final_url,
        "text": None,
        "scraped_at": scraped_at,
        "error": str(msg).split("\n")[0][:300],
    }


async def crawl_all(companies: list[dict], output_path: Path, progress_cb=None):
    semaphore = asyncio.Semaphore(CONCURRENCY)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        async def process(company_info: dict, idx: int) -> dict:
            async with semaphore:
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    ignore_https_errors=True,
                )
                context.set_default_timeout(NAV_TIMEOUT)
                context.set_default_navigation_timeout(NAV_TIMEOUT)
                try:
                    page = await context.new_page()
                    result = await asyncio.wait_for(
                        scrape_company(
                            page, company_info["company"], company_info["careers_url"],
                        ),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    result = _error(
                        company_info["company"],
                        company_info["careers_url"],
                        datetime.now(timezone.utc).isoformat(),
                        "total timeout exceeded",
                    )
                except Exception as exc:
                    result = _error(
                        company_info["company"],
                        company_info["careers_url"],
                        datetime.now(timezone.utc).isoformat(),
                        f"unexpected error: {type(exc).__name__}: {exc}",
                    )
                finally:
                    # Brief grace period lets Playwright settle in-flight ops
                    # before we tear down the context, preventing leaked futures.
                    await asyncio.sleep(0.5)
                    try:
                        await context.close()
                    except Exception:
                        pass

                if progress_cb:
                    progress_cb(idx + 1, result.get("error"))
                return result

        tasks = [process(c, i) for i, c in enumerate(companies)]

        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                await f.write(json.dumps(result, ensure_ascii=False) + "\n")

        await browser.close()
