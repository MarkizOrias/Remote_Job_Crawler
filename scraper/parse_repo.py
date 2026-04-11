"""Stage 1: Clone remote-jobs repo and extract company career URLs."""

import re
import subprocess
from pathlib import Path


REPO_URL = "https://github.com/remoteintech/remote-jobs"
REPO_DIR = Path("remote-jobs")


def clone_or_update_repo():
    if REPO_DIR.exists():
        subprocess.run(["git", "-C", str(REPO_DIR), "pull", "--ff-only"], check=False, capture_output=True)
    else:
        subprocess.run(["git", "clone", "--depth=1", REPO_URL, str(REPO_DIR)], check=True)


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter fields (key: value) between --- delimiters."""
    fields = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return fields
    for line in m.group(1).splitlines():
        kv = re.match(r'^(\w+):\s*["\']?(.*?)["\']?\s*$', line)
        if kv:
            fields[kv.group(1)] = kv.group(2).strip()
    return fields


def parse_companies() -> list[dict]:
    clone_or_update_repo()
    companies_dir = REPO_DIR / "company-profiles"
    if not companies_dir.exists():
        companies_dir = REPO_DIR / "src" / "companies"
    if not companies_dir.exists():
        raise FileNotFoundError(f"Could not find companies directory in {REPO_DIR}")

    results = []
    for md_file in sorted(companies_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        fm = _parse_frontmatter(text)

        company_name = fm.get("title") or md_file.stem.replace("-", " ").title()
        url = fm.get("careers_url") or fm.get("website")

        if not url:
            continue
        if not url.startswith("http"):
            url = "https://" + url

        results.append({"company": company_name, "careers_url": url})

    return results
