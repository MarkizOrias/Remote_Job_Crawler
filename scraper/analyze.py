"""Analyze scraped_roles.json: classify failures and write failure_report.md."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


CATEGORIES: list[tuple[str, re.Pattern]] = [
    ("captcha_or_login_wall", re.compile(r"captcha|cloudflare|access denied|forbidden|403|sign[- ]?in|log[- ]?in|verify you are human|just a moment", re.I)),
    ("connection_refused", re.compile(r"connection.*(refused|reset|closed)|ECONNREFUSED|ECONNRESET|net::ERR_CONNECTION", re.I)),
    ("dns_error", re.compile(r"name not resolved|getaddrinfo|net::ERR_NAME|ENOTFOUND|DNS", re.I)),
    ("ssl_error", re.compile(r"SSL|TLS|certificate|net::ERR_CERT", re.I)),
    ("redirect_loop", re.compile(r"too many redirects|net::ERR_TOO_MANY_REDIRECTS|redirect loop", re.I)),
    ("http_404", re.compile(r"\b404\b|not found|page not found", re.I)),
    ("http_5xx", re.compile(r"\b5\d\d\b|server error|bad gateway|gateway timeout|service unavailable", re.I)),
    ("timeout_total", re.compile(r"total timeout exceeded", re.I)),
    ("timeout_navigation", re.compile(r"timeout.*navigat|net::ERR_TIMED_OUT|Timeout \d+ms exceeded", re.I)),
    ("aborted", re.compile(r"net::ERR_ABORTED|aborted", re.I)),
    ("insufficient_content", re.compile(r"insufficient_content", re.I)),
]


def categorize(error: str | None) -> str:
    if not error:
        return "ok"
    for name, pat in CATEGORIES:
        if pat.search(error):
            return name
    return "other"


def domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def report(records: Iterable[dict]) -> str:
    records = list(records)
    total = len(records)
    successes = [r for r in records if not r.get("error") and r.get("text")]
    failures = [r for r in records if r.get("error")]
    cats = Counter(categorize(r.get("error")) for r in failures)
    domains = Counter(domain(r.get("careers_url")) for r in failures)

    lines: list[str] = []
    pct = (len(successes) / total * 100) if total else 0
    lines.append(f"# Failure Report\n")
    lines.append(f"- Total: **{total}**")
    lines.append(f"- Success: **{len(successes)} ({pct:.1f}%)**")
    lines.append(f"- Failure: **{len(failures)}**\n")

    lines.append("## By category\n")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for k, v in cats.most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Top failure domains (top 25)\n")
    lines.append("| Domain | Count |")
    lines.append("|--------|-------|")
    for k, v in domains.most_common(25):
        if not k:
            continue
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Sample failures (per category, up to 8 each)\n")
    by_cat: dict[str, list[dict]] = {}
    for r in failures:
        by_cat.setdefault(categorize(r.get("error")), []).append(r)
    for cat, rs in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"### {cat} ({len(rs)})\n")
        for r in rs[:8]:
            lines.append(f"- **{r['company']}** -> {r['careers_url']}  \n  `{r.get('error')}`")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    path = Path("data/scraped_roles.json")
    records = load(path)
    out = Path("data/failure_report.md")
    out.write_text(report(records), encoding="utf-8")
    print(f"Wrote {out}")
    fails = sum(1 for r in records if r.get("error"))
    print(f"Total {len(records)} | failures {fails}")


if __name__ == "__main__":
    main()
