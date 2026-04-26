"""Stage 2+3: Crawl career pages and extract raw listing text."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from .heuristics import ATS_HOST_RE, find_jobs_url

log = logging.getLogger(__name__)

CONCURRENCY = 10
NAV_TIMEOUT = 25_000
NETWORKIDLE_GRACE = 8_000  # extra wait for JS after DOM loads
HYDRATION_WAIT = 3.5       # extra sleep when text is short, to allow JS to mount
DELAY_BETWEEN_NAV = 1.0
PER_COMPANY_TIMEOUT = 45    # total wall time per company

# Common selectors that, if present, indicate the listings page has hydrated.
HYDRATION_SELECTORS = (
    "[data-qa='posting-name']",        # Lever
    "div.opening",                     # Lever (legacy)
    "div.posting",                     # Lever (legacy)
    "[data-mapped='true']",            # Greenhouse new
    ".opening",                        # Greenhouse legacy
    "div.job-board-content",           # Greenhouse embed
    "[data-automation-id='jobTitle']", # Workday
    "a[href*='/jobs/']",               # Generic
    "a[href*='/job/']",                # Generic
    "li[class*='job']",                # Generic listing
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Tiny bit of fingerprint hardening — flips webdriver=true to undefined and
# fills in a couple of properties bot-detection libraries (incl. Cloudflare's)
# spot-check first. Not "stealth-mode" complete, just enough to slip past the
# naive checks that account for most third-party 403s in the dataset.
STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || {runtime: {}};
"""

EXTRA_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

# Obvious non-job noise that clutters the links array (social, legal, auth).
# Kept narrow — match_roles.py does the final job-link filtering downstream.
LINK_NOISE_RE = re.compile(
    r"("
    r"mailto:|javascript:|tel:|"
    r"(?:twitter|x|facebook|instagram|youtube|linkedin|bsky|tiktok|threads|pinterest|reddit|medium)\.com|"
    r"bsky\.app|t\.me|discord\.(?:gg|com)|"
    r"/(?:cookie|privacy|terms|legal|accessibility|gdpr|imprint|login|signin|sign-in|sign_in|logout|subscribe|newsletter)"
    r")",
    re.IGNORECASE,
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

# Some sites (Cards Against Humanity, YAZIO, Discourse) put the entire visible
# content inside <footer> or <header>; aggressive stripping leaves <200 chars.
# This light-strip variant only removes <script>/<style>/<noscript> so we still
# get something. Used as a fallback when the aggressive pass returned too little.
LIGHT_STRIP_JS = """
() => {
    if (!document.body) return '';
    const clone = document.body.cloneNode(true);
    for (const tag of ['script','style','noscript']) {
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


async def _navigate(page, url: str) -> int | None:
    """Navigate with domcontentloaded, then briefly try networkidle.

    Returns the HTTP status code from the navigation response, or None if no
    response was captured. Used to classify dead pages (404/403/5xx).
    """
    response = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    try:
        await page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_GRACE)
    except Exception:
        pass  # Best-effort; DOM is already loaded
    return response.status if response else None


async def _wait_for_hydration(page) -> None:
    """If a known job-listing selector is present, await it; otherwise sleep briefly.

    Many ATS pages (Lever, Greenhouse, Workday) render a near-empty <body> until
    XHR-fetched job data hydrates. Without this, page.inner_text returns <200 chars
    and we mis-classify the page as `insufficient_content`.
    """
    try:
        await page.wait_for_selector(
            ", ".join(HYDRATION_SELECTORS),
            timeout=4_000,
            state="attached",
        )
    except Exception:
        pass
    await asyncio.sleep(HYDRATION_WAIT)


def _rewrite_greenhouse_embed(url: str) -> str | None:
    """Greenhouse embed URLs hide the canonical board behind validityToken redirects.

    Rewriting `boards.greenhouse.io/embed/job_board?for=foo&...` to the direct
    `job-boards.greenhouse.io/foo` board avoids the iframe + token gymnastics.
    """
    m = re.search(r"greenhouse\.io/embed/job_board[^#]*?[?&]for=([\w.-]+)", url, re.I)
    if not m:
        return None
    slug = m.group(1)
    return f"https://job-boards.greenhouse.io/{slug}"


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _clean_text(text: str) -> str:
    """Trim per-line whitespace and collapse runs of blank lines."""
    out: list[str] = []
    blank = 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            # Collapse runs of internal whitespace (tabs, multiple spaces).
            out.append(re.sub(r"[ \t]{2,}", " ", line))
    return "\n".join(out).strip()


def _filter_links(links: list[dict]) -> list[dict]:
    """Drop obvious noise and dedupe, keeping relative order."""
    out: list[dict] = []
    seen: set[str] = set()
    for link in links:
        href = (link.get("href") or "").strip()
        text = (link.get("text") or "").strip()
        if not href or not text or len(text) < 3:
            continue
        if href.startswith("#") or href in seen:
            continue
        if LINK_NOISE_RE.search(href):
            continue
        seen.add(href)
        out.append({"text": text, "href": href})
    return out


async def scrape_company(page, company: str, careers_url: str) -> dict:
    scraped_at = _now_iso()
    try:
        try:
            status = await _navigate(page, careers_url)
        except Exception as e:
            return _error(company, careers_url, scraped_at, f"timeout navigating to careers page: {e}")

        await asyncio.sleep(DELAY_BETWEEN_NAV)

        # Greenhouse "embed" pages need to be rewritten to the canonical board
        # before we even try to find the jobs URL — the embed itself hides the
        # listings behind a validityToken iframe that we can't reach.
        rewritten = _rewrite_greenhouse_embed(page.url)
        if rewritten and rewritten != page.url:
            try:
                status = await _navigate(page, rewritten)
                await asyncio.sleep(DELAY_BETWEEN_NAV)
            except Exception:
                pass

        try:
            jobs_url = await find_jobs_url(page, page.url)
        except Exception:
            jobs_url = None

        final_url = page.url
        final_status = status

        if jobs_url and jobs_url != page.url:
            try:
                final_status = await _navigate(page, jobs_url)
                final_url = page.url
                await asyncio.sleep(DELAY_BETWEEN_NAV)
            except Exception:
                pass

        # The discovered jobs URL itself might be a Greenhouse "embed" URL; rewrite
        # to the canonical board so we get the actual listings instead of the embed
        # token shell. (Initial rewrite earlier handles careers pages that already
        # land on an embed URL; this second pass handles ones we navigated to.)
        rewritten = _rewrite_greenhouse_embed(page.url)
        if rewritten and rewritten != page.url:
            try:
                final_status = await _navigate(page, rewritten)
                final_url = page.url
                await asyncio.sleep(DELAY_BETWEEN_NAV)
            except Exception:
                pass

        # First extraction attempt.
        try:
            text = await page.evaluate(STRIP_TAGS_JS)
        except Exception as e:
            return _error(company, careers_url, scraped_at, f"text extraction failed: {e}", final_url)

        cleaned = _clean_text(text or "")

        # If the page looks empty, give the JS another moment to mount and retry.
        if len(cleaned) < 200:
            try:
                await _wait_for_hydration(page)
                text = await page.evaluate(STRIP_TAGS_JS)
                cleaned = _clean_text(text or "")
            except Exception:
                pass

        # Final fallback: some sites put their content inside <footer>/<header>
        # which the aggressive strip removes. Re-extract without that strip; we
        # accept anything with >= 100 chars on a 200 OK page, since "no current
        # openings" pages are short but still valid scrape results.
        if len(cleaned) < 200:
            try:
                light = await page.evaluate(LIGHT_STRIP_JS)
                light_clean = _clean_text(light or "")
                threshold = 100 if (final_status and final_status < 400) else 200
                if len(light_clean) >= threshold:
                    cleaned = light_clean
            except Exception:
                pass

        try:
            raw_links = await page.evaluate(EXTRACT_LINKS_JS)
        except Exception:
            raw_links = []

        # Acceptance threshold:
        # - 50 chars on a known ATS host with HTTP 200 ("no current openings"
        #   on a Greenhouse/Lever board is a *valid* scrape, just an empty one)
        # - 100 chars on any other healthy page
        # - 200 chars otherwise (preserves the original spec)
        if final_status and final_status < 400 and ATS_HOST_RE.search(final_url or ""):
            min_chars = 50
        elif final_status and final_status < 400:
            min_chars = 100
        else:
            min_chars = 200
        if len(cleaned) < min_chars:
            # Be specific when the page is gone vs. just empty — both cases
            # are usually unrecoverable but the report should distinguish them.
            err = _status_error_label(final_status) or "insufficient_content"
            return _error(company, careers_url, scraped_at, err, final_url)

        return {
            "company": company,
            "careers_url": careers_url,
            "final_url": final_url,
            "scraped_at": scraped_at,
            "error": None,
            "text": cleaned,
            "links": _filter_links(raw_links),
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass


def _status_error_label(status: int | None) -> str | None:
    """Map an HTTP status code to a stable, greppable error label."""
    if status is None:
        return None
    if status == 404:
        return "http_404 page not found"
    if status == 403:
        return "http_403 forbidden"
    if status == 401:
        return "http_401 unauthorized"
    if 500 <= status <= 599:
        return f"http_{status} server error"
    return None


def _error(company, careers_url, scraped_at, msg, final_url=None):
    return {
        "company": company,
        "careers_url": careers_url,
        "final_url": final_url,
        "scraped_at": scraped_at,
        "error": str(msg).split("\n")[0][:300],
        "text": None,
        "links": [],
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
                    locale="en-US",
                    viewport={"width": 1366, "height": 768},
                    extra_http_headers=EXTRA_HEADERS,
                )
                await context.add_init_script(STEALTH_INIT_JS)
                context.set_default_timeout(NAV_TIMEOUT)
                context.set_default_navigation_timeout(NAV_TIMEOUT)
                try:
                    page = await context.new_page()
                    result = await asyncio.wait_for(
                        scrape_company(
                            page, company_info["company"], company_info["careers_url"],
                        ),
                        timeout=PER_COMPANY_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    result = _error(
                        company_info["company"],
                        company_info["careers_url"],
                        _now_iso(),
                        "total timeout exceeded",
                    )
                except Exception as exc:
                    result = _error(
                        company_info["company"],
                        company_info["careers_url"],
                        _now_iso(),
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
        results: list[dict] = []
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)

        await browser.close()

    # Sort by company so the output is stable across runs.
    results.sort(key=lambda r: (r.get("company") or "").lower())
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return results
