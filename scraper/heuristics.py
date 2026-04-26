"""Heuristics for finding job listing links and detecting ATS embeds."""

import re
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page


JOBS_KEYWORD_RE = re.compile(
    r"(see|view|browse|search|explore|find|open|all|current|available)\s+"
    r"(?:our\s+)?(jobs|positions|roles|openings|opportunities|vacancies)",
    re.IGNORECASE,
)

JOBS_PATH_RE = re.compile(
    r"/(jobs|positions|openings|vacancies|opportunities|"
    r"careers/(search|listings|jobs|open|all|positions|browse|view)|"
    r"join|work-with-us|join-us|hiring|join-our-team)(/|$|\?)",
    re.IGNORECASE,
)

# Hosted ATS URLs — used both for iframe src and direct anchor href detection.
# Broader than the original iframe-only regex so we can also follow direct anchor links.
ATS_HOST_RE = re.compile(
    r"("
    r"boards\.greenhouse\.io|job-boards\.greenhouse\.io|[\w-]+\.greenhouse\.io|"
    r"jobs\.lever\.co|"
    r"[\w-]+\.myworkdayjobs\.com|myworkdayjobs\.com|"
    r"app\.dover\.io|"
    r"jobs\.ashbyhq\.com|[\w-]+\.ashbyhq\.com|"
    r"apply\.workable\.com|jobs\.workable\.com|"
    r"[\w-]+\.bamboohr\.com|"
    r"(?:careers|jobs)\.smartrecruiters\.com|"
    r"jobs\.jobvite\.com|[\w-]+\.jobvite\.com|"
    r"[\w-]+\.recruitee\.com|"
    r"[\w-]+\.teamtailor\.com|"
    r"[\w-]+\.breezy\.hr|"
    r"jobs\.personio\.com|jobs\.personio\.de|[\w-]+\.jobs\.personio\.com|"
    r"[\w-]+\.applytojob\.com|"
    r"[\w-]+\.comeet\.co|"
    r"[\w-]+\.zohorecruit\.com|"
    r"[\w-]+\.pinpointhq\.com|"
    r"[\w-]+\.bullhorncareers\.com|"
    r"[\w-]+\.icims\.com|"
    r"[\w-]+\.taleo\.net|"
    r"[\w-]+\.successfactors\.com|"
    r"[\w-]+\.eightfold\.ai|"
    r"app\.beamery\.com|[\w-]+\.beamery\.com|"
    r"freshteam\.com/jobs|[\w-]+\.freshteam\.com|"
    r"join\.com/companies"
    r")",
    re.IGNORECASE,
)

# Skip hrefs that are obviously auth/account flows — these are NOT job pages
# even when they contain "/jobs" in a returnUrl=... query parameter.
AUTH_RE = re.compile(
    r"/(register|signup|sign[-_]?up|signin|sign[-_]?in|login|log[-_]?in|"
    r"logout|account|auth|sso|oauth|verify|forgot|reset)(/|$|\?)",
    re.IGNORECASE,
)


def _href_path(href: str, base_url: str) -> str:
    """Return just the URL *path* (no query, no fragment) for matching against."""
    try:
        u = urlparse(_resolve(href, base_url))
        return u.path or "/"
    except Exception:
        return href


async def find_jobs_url(page: Page, base_url: str) -> str | None:
    """Return the best candidate jobs listing URL, or None."""

    # 1. Check for ATS iframes
    iframe_url = await _detect_ats_iframe(page)
    if iframe_url:
        return iframe_url

    # 2. Scan <a> tags
    anchors = await page.eval_on_selector_all(
        "a[href]",
        """els => els.map(el => ({text: el.innerText.trim(), href: el.getAttribute('href')}))""",
    )

    # 2a. Direct ATS hosts — strongest signal
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        full = _resolve(href, base_url)
        if ATS_HOST_RE.search(full):
            return full

    # 2b. Anchor text matches "see/view/browse jobs"
    for a in anchors:
        text = (a.get("text") or "").strip()
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        full = _resolve(href, base_url)
        # Don't follow auth flows even if the link text mentions jobs.
        if AUTH_RE.search(urlparse(full).path):
            continue
        if JOBS_KEYWORD_RE.search(text):
            return full

    # 2c. Href path pattern — only match against the path, not query/fragment.
    # The original regex would match `/register?returnUrl=/jobs` as a job link;
    # restricting to the path prevents that false positive.
    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        full = _resolve(href, base_url)
        path = urlparse(full).path
        if AUTH_RE.search(path):
            continue
        if JOBS_PATH_RE.search(path):
            return full

    return None


async def _detect_ats_iframe(page: Page) -> str | None:
    iframes = await page.eval_on_selector_all(
        "iframe[src]",
        "els => els.map(el => el.getAttribute('src'))",
    )
    for src in iframes:
        if src and ATS_HOST_RE.search(src):
            if src.startswith("//"):
                return "https:" + src
            return src
    return None


def _resolve(href: str, base_url: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)
