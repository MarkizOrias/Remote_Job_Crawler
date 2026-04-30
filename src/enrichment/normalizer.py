"""Normalize job titles, tags, locations, and experience levels."""

import re

# Common title noise to strip
_TITLE_NOISE = re.compile(
    r"\s*[\(\[].*(remote|hybrid|contract|full[- ]?time|part[- ]?time|m/f/d|m/w/d|h/f|all genders).*[\)\]]",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s+")

# Experience level detection
_EXPERIENCE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("junior", re.compile(r"\b(junior|jr\.?|entry[- ]?level|associate)\b", re.IGNORECASE)),
    ("mid", re.compile(r"\b(mid[- ]?level|intermediate)\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(senior|sr\.?|principal|staff)\b", re.IGNORECASE)),
    ("lead", re.compile(r"\b(lead|head|director|vp|chief|manager)\b", re.IGNORECASE)),
]

# Location normalization
_LOCATION_MAP: dict[str, str] = {
    "worldwide": "Remote (Worldwide)",
    "anywhere": "Remote (Worldwide)",
    "global": "Remote (Worldwide)",
    "remote": "Remote",
}


def normalize_title(title: str) -> str:
    """Clean up a job title: strip parenthetical noise, normalize whitespace."""
    title = _TITLE_NOISE.sub("", title)
    title = _WHITESPACE.sub(" ", title).strip()
    return title


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, strip, deduplicate tags."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        t = tag.strip().lower()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def normalize_location(location: str) -> str:
    """Normalize location strings to a consistent format."""
    loc = location.strip()
    if not loc:
        return "Remote"

    loc_lower = loc.lower()
    for key, replacement in _LOCATION_MAP.items():
        if loc_lower == key or loc_lower == f"remote - {key}":
            return replacement

    if "remote" not in loc_lower:
        return f"Remote ({loc})"

    return loc


def detect_experience_level(title: str, description: str = "") -> str | None:
    """Infer experience level from title (primary) or description (fallback)."""
    for level, pattern in _EXPERIENCE_PATTERNS:
        if pattern.search(title):
            return level
    for level, pattern in _EXPERIENCE_PATTERNS:
        if pattern.search(description[:500]):
            return level
    return None


def normalize_job_type(raw: str | None) -> str | None:
    """Map raw job type strings to canonical values."""
    if not raw:
        return None
    raw_lower = raw.lower().strip()
    mapping = {
        "full_time": "full-time",
        "full time": "full-time",
        "fulltime": "full-time",
        "part_time": "part-time",
        "part time": "part-time",
        "parttime": "part-time",
        "freelance": "contract",
        "contractor": "contract",
    }
    return mapping.get(raw_lower, raw_lower)
