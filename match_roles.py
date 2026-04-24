"""Match scraped job listings against profile.json and rank by fit."""

import json
import re
from pathlib import Path


def load_profile() -> dict:
    return json.loads(Path("profile.json").read_text(encoding="utf-8"))


def load_scraped() -> list[dict]:
    results = []
    for line in Path("data/scraped_roles.jsonl").read_text(encoding="utf-8").strip().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("text") and not r.get("error"):
            results.append(r)
    return results


# Keywords that indicate a link points to an individual job posting
JOB_LINK_RE = re.compile(
    r"(analyst|specialist|engineer|manager|lead|director|coordinator|associate|"
    r"officer|developer|architect|admin|accountant|operation|finance|data|"
    r"reconcil|settle|trade|report|automat|python|support)",
    re.IGNORECASE,
)

# URL patterns for known ATS job detail pages
ATS_JOB_RE = re.compile(
    r"(greenhouse\.io/.+/jobs/|lever\.co/.+/|ashbyhq\.com/.+/|"
    r"myworkdayjobs\.com/.+/job/|workable\.com/.+/j/|"
    r"bamboohr\.com/careers/|/jobs?/\d|/positions?/\d|/careers/.+/\d)",
    re.IGNORECASE,
)


def extract_job_links(links: list[dict], text_lower: str, profile: dict) -> list[dict]:
    """Filter page links down to those likely pointing to relevant job postings."""
    prefs = profile["preferences"]
    relevant = []

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")
        combined = (text + " " + href).lower()

        # Skip generic nav/footer links
        if not text or len(text) < 3:
            continue
        if any(skip in combined for skip in ["login", "sign in", "privacy", "cookie", "terms of"]):
            continue

        # Check if link text or URL matches job-related patterns
        is_job = bool(JOB_LINK_RE.search(text)) or bool(ATS_JOB_RE.search(href))
        if not is_job:
            continue

        # Check for exclude keywords
        if any(kw.lower() in combined for kw in prefs["exclude_keywords"]):
            continue

        relevant.append({"title": text.strip(), "url": href})

    return relevant


def score_company(text_lower: str, profile: dict) -> dict:
    """Score a scraped page against the profile. Returns score breakdown."""
    prefs = profile["preferences"]
    cv = profile["cv"]

    scores = {}

    # 1. Preferred keywords (2 points each)
    kw_hits = []
    for kw in prefs["preferred_keywords"]:
        if kw.lower() in text_lower:
            kw_hits.append(kw)
    scores["preferred_keywords"] = kw_hits
    scores["preferred_kw_score"] = len(kw_hits) * 2

    # 2. Target role title matches (5 points each)
    role_hits = []
    for role in prefs["roles"]:
        # Match individual significant words from role titles
        words = [w for w in role.lower().split() if len(w) > 3]
        if any(w in text_lower for w in words):
            role_hits.append(role)
    scores["role_title_hits"] = role_hits
    scores["role_title_score"] = len(role_hits) * 5

    # 3. Operations/finance skill matches (3 points each)
    ops_hits = []
    for skill in cv["skills"]["operations_finance"]:
        if skill.lower() in text_lower:
            ops_hits.append(skill)
    scores["ops_finance_hits"] = ops_hits
    scores["ops_finance_score"] = len(ops_hits) * 3

    # 4. Technical skill matches (2 points each)
    tech_hits = []
    for skill in cv["skills"]["technical"]:
        # Exact word boundary match for short terms like "Python", "CSS"
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            tech_hits.append(skill)
    scores["tech_hits"] = tech_hits
    scores["tech_score"] = len(tech_hits) * 2

    # 5. Methodology matches (2 points each)
    method_hits = []
    for skill in cv["skills"]["methodology"]:
        if skill.lower() in text_lower:
            method_hits.append(skill)
    scores["method_hits"] = method_hits
    scores["method_score"] = len(method_hits) * 2

    # 6. Exclude keyword penalty (-100 each, effectively disqualifies)
    exclude_hits = []
    for kw in prefs["exclude_keywords"]:
        if kw.lower() in text_lower:
            exclude_hits.append(kw)
    scores["exclude_hits"] = exclude_hits
    scores["exclude_penalty"] = len(exclude_hits) * -100

    # Total
    scores["total"] = (
        scores["preferred_kw_score"]
        + scores["role_title_score"]
        + scores["ops_finance_score"]
        + scores["tech_score"]
        + scores["method_score"]
        + scores["exclude_penalty"]
    )

    return scores


def main():
    profile = load_profile()
    scraped = load_scraped()
    exclude_companies = [c.lower() for c in profile["preferences"].get("exclude_companies", [])]

    print(f"Loaded {len(scraped)} successful scrapes. Scoring...\n")

    results = []
    for entry in scraped:
        company = entry["company"]
        if company.lower() in exclude_companies:
            continue

        text_lower = entry["text"].lower()
        scores = score_company(text_lower, profile)

        if scores["total"] > 0:
            job_links = extract_job_links(
                entry.get("links", []), text_lower, profile,
            )
            results.append({
                "company": company,
                "careers_url": entry["careers_url"],
                "final_url": entry["final_url"],
                "job_links": job_links,
                "scores": scores,
            })

    results.sort(key=lambda r: r["scores"]["total"], reverse=True)

    # Print top matches
    print(f"{'Rank':<5} {'Score':<6} {'Company':<35} {'Role Hits'}")
    print("-" * 110)

    for i, r in enumerate(results[:30], 1):
        s = r["scores"]
        role_summary = ", ".join(s["role_title_hits"][:3]) or "-"
        kw_summary = ", ".join(s["preferred_keywords"][:4])
        print(f"{i:<5} {s['total']:<6} {r['company'][:34]:<35} {role_summary}")
        print(f"{'':5} {'':6} Keywords: {kw_summary}")
        if s["ops_finance_hits"]:
            print(f"{'':5} {'':6} Ops/Finance: {', '.join(s['ops_finance_hits'])}")
        if s["tech_hits"]:
            print(f"{'':5} {'':6} Tech: {', '.join(s['tech_hits'])}")
        if s["exclude_hits"]:
            print(f"{'':5} {'':6} ** EXCLUDED: {', '.join(s['exclude_hits'])}")
        print(f"{'':5} {'':6} URL: {r['final_url']}")
        if r.get("job_links"):
            for jl in r["job_links"][:5]:
                print(f"{'':5} {'':6}   -> {jl['title'][:60]}")
                print(f"{'':5} {'':6}      {jl['url'][:120]}")
        print()

    # Save full results to JSON
    out_path = Path("data/matched_roles.json")
    out_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nFull results ({len(results)} matches) saved to {out_path}")


if __name__ == "__main__":
    main()
