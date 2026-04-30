"""GitHub company directory parser — 3 repos into the companies table."""

import logging
import re
from pathlib import Path

import httpx

from src.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
RAW_GH = "https://raw.githubusercontent.com"


class GitHubListsScraper(BaseScraper):
    name = "github_lists"
    base_url = GITHUB_API

    async def scrape(self) -> list[Job]:
        """Parse all three GitHub repos. Returns empty Job list
        (companies go into companies table via separate path)."""
        companies: list[dict] = []

        companies.extend(await self._parse_remoteintech())
        companies.extend(await self._parse_yanirs())
        companies.extend(await self._parse_fireball())

        logger.info("[github_lists] Total companies parsed: %d", len(companies))
        self._save_companies(companies)
        return []

    async def _parse_remoteintech(self) -> list[dict]:
        """remoteintech/remote-jobs: individual markdown files with YAML frontmatter."""
        logger.info("[github_lists] Parsing remoteintech/remote-jobs...")
        try:
            listing_json = await self._get_json(
                f"{GITHUB_API}/repos/remoteintech/remote-jobs/contents/src/companies"
            )
        except Exception as exc:
            logger.warning("[github_lists] Failed to list remoteintech files: %s", exc)
            return []

        if not isinstance(listing_json, list):
            logger.warning("[github_lists] Unexpected remoteintech API response")
            return []

        companies: list[dict] = []
        for i, file_info in enumerate(listing_json):
            if not file_info.get("name", "").endswith(".md"):
                continue
            try:
                raw_url = file_info.get("download_url", "")
                if not raw_url:
                    continue
                text = await self._get(raw_url)
                company = self._parse_remoteintech_file(text)
                if company:
                    company["source"] = "remoteintech"
                    companies.append(company)
            except Exception:
                logger.debug("[github_lists] Failed to parse %s", file_info.get("name"), exc_info=True)

            if (i + 1) % 100 == 0:
                logger.info("[github_lists] remoteintech: %d/%d files processed", i + 1, len(listing_json))

        logger.info("[github_lists] remoteintech: %d companies parsed", len(companies))
        return companies

    def _parse_remoteintech_file(self, text: str) -> dict | None:
        """Parse YAML frontmatter from a remoteintech company file."""
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return None

        fm = m.group(1)
        fields: dict = {}

        for line in fm.splitlines():
            kv = re.match(r'^(\w[\w_]*):\s*["\']?(.*?)["\']?\s*$', line)
            if kv:
                fields[kv.group(1)] = kv.group(2).strip()

        name = fields.get("title")
        if not name:
            return None

        tech_list = re.findall(r"^\s+-\s+(.+)$", fm, re.MULTILINE)

        return {
            "name": name,
            "website": fields.get("website"),
            "careers_url": fields.get("careers_url"),
            "remote_policy": fields.get("remote_policy"),
            "size": fields.get("company_size"),
            "tech_stack": tech_list,
        }

    async def _parse_yanirs(self) -> list[dict]:
        """yanirs/established-remote: markdown table in README."""
        logger.info("[github_lists] Parsing yanirs/established-remote...")
        try:
            text = await self._get(f"{RAW_GH}/yanirs/established-remote/master/README.md")
        except Exception as exc:
            logger.warning("[github_lists] Failed to fetch yanirs README: %s", exc)
            return []

        companies: list[dict] = []
        table_re = re.compile(
            r"\[([^\]]+)\]\((https?://[^\)]+)\)\s*\|\s*([^|]+)\|\s*([^|]+)"
        )

        for match in table_re.finditer(text):
            name = match.group(1).strip()
            website = match.group(2).strip()
            _business = match.group(3).strip()
            tech_raw = match.group(4).strip()
            tech_list = [t.strip() for t in tech_raw.split(",") if t.strip()]

            companies.append({
                "name": name,
                "website": website,
                "careers_url": None,
                "remote_policy": "fully-remote",
                "size": None,
                "tech_stack": tech_list,
                "description": _business,
                "source": "yanirs",
            })

        logger.info("[github_lists] yanirs: %d companies parsed", len(companies))
        return companies

    async def _parse_fireball(self) -> list[dict]:
        """fireball787b/awesome-remote-companies: numbered list in README."""
        logger.info("[github_lists] Parsing fireball787b/awesome-remote-companies...")
        try:
            text = await self._get(f"{RAW_GH}/fireball787b/awesome-remote-companies/main/README.md")
        except Exception as exc:
            logger.warning("[github_lists] Failed to fetch fireball README: %s", exc)
            return []

        companies: list[dict] = []
        entry_re = re.compile(
            r"\[([^\]]+)\]\((https?://[^\)]+)\)\s*[-–—]\s*([^<\n]+)"
        )

        for match in entry_re.finditer(text):
            name = match.group(1).strip()
            url = match.group(2).strip()
            description = match.group(3).strip().rstrip(".")

            if name.lower() in ("awesome", "values", "culture", "glassdoor"):
                continue

            companies.append({
                "name": name,
                "website": None,
                "careers_url": url,
                "remote_policy": "fully-remote",
                "size": None,
                "tech_stack": [],
                "description": description,
                "source": "fireball",
            })

        logger.info("[github_lists] fireball: %d companies parsed", len(companies))
        return companies

    def _save_companies(self, companies: list[dict]) -> None:
        """Insert parsed companies into the database."""
        from src.db.connection import get_connection
        from src.db.queries import upsert_company

        conn = get_connection()
        saved = 0
        for company in companies:
            try:
                upsert_company(conn, company)
                saved += 1
            except Exception:
                logger.debug("Failed to upsert company %s", company.get("name"), exc_info=True)
        conn.close()
        logger.info("[github_lists] Saved %d companies to database", saved)
