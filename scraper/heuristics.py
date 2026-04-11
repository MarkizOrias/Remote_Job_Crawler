"""Heuristics for finding job listing links and detecting ATS embeds."""

import re
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page


JOBS_KEYWORD_RE = re.compile(
    r"(see|view|browse|search|explore|find|open)\s+(jobs|positions|roles|openings|opportunities)",
    re.IGNORECASE,
)

JOBS_PATH_RE = re.compile(
    r"/(jobs|positions|openings|careers/(search|listings|jobs|open|all)|join|work-with-us)(/|$)",
    re.IGNORECASE,
)

ATS_IFRAME_RE = re.compile(
    r"(boards\.greenhouse\.io|jobs\.lever\.co|[\w-]+\.myworkdayjobs\.com|"
    r"[\w-]+\.greenhouse\.io|app\.dover\.io|jobs\.ashbyhq\.com|"
    r"apply\.workable\.com|[\w-]+\.bamboohr\.com)",
    re.IGNORECASE,
)


async def find_jobs_url(page: Page, base_url: str) -> str | None:
    """Return the best candidate jobs listing URL, or None."""

    # 1. Check for ATS iframes
    iframe_url = await _detect_ats_iframe(page)
    if iframe_url:
        return iframe_url

    # 2. Scan <a> tags by link text
    anchors = await page.eval_on_selector_all(
        "a[href]",
        """els => els.map(el => ({text: el.innerText.trim(), href: el.getAttribute('href')}))""",
    )
    for a in anchors:
        text = (a.get("text") or "").strip()
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        if JOBS_KEYWORD_RE.search(text):
            return _resolve(href, base_url)

    # 3. Scan <a> tags by href path pattern
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        if JOBS_PATH_RE.search(href):
            return _resolve(href, base_url)

    return None


async def _detect_ats_iframe(page: Page) -> str | None:
    iframes = await page.eval_on_selector_all(
        "iframe[src]",
        "els => els.map(el => el.getAttribute('src'))",
    )
    for src in iframes:
        if src and ATS_IFRAME_RE.search(src):
            return src if src.startswith("http") else "https:" + src
    return None


def _resolve(href: str, base_url: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)
