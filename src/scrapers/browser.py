"""Shared Playwright browser management for JS-rendered scrapers."""

import logging
import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config import USER_AGENTS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_browser() -> AsyncGenerator[Browser, None]:
    """Launch a headless Chromium instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def get_page(browser: Browser, *, timeout: int = 30000) -> AsyncGenerator[Page, None]:
    """Create a browser context + page with realistic headers."""
    context: BrowserContext = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )
    context.set_default_timeout(timeout)
    page = await context.new_page()
    try:
        yield page
    finally:
        await context.close()


async def safe_goto(page: Page, url: str, *, wait_until: str = "domcontentloaded") -> bool:
    """Navigate to a URL, returning True on success."""
    try:
        await page.goto(url, wait_until=wait_until)
        return True
    except Exception as exc:
        logger.warning("Navigation failed for %s: %s", url, exc)
        return False


async def extract_visible_text(page: Page) -> str:
    """Get visible text from page, stripping nav/footer/script elements."""
    return await page.evaluate("""() => {
        for (const sel of ['script','style','nav','footer','header','noscript']) {
            document.querySelectorAll(sel).forEach(el => el.remove());
        }
        return document.body ? document.body.innerText : '';
    }""")
