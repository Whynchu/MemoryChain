"""
WHYNN log parser.

Splits III_DAILY_LOGS.txt into individual day entries, then parses each
entry into named sections. Purely deterministic — no LLM required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


# Section header keywords (must appear at line start, followed by colon)
SECTION_KEYS = [
    "SYSTEM METRICS",
    "BREATHWORK & PHYSICAL METRICS",
    "TRAINING EXECUTION",
    "NUTRITION & HYDRATION",
    "BUFFS TRIGGERED",
    "XP AWARDS",
    "SYSTEM NOTES",
    "SIGN-OFF",
]

# Matches "April 7, 2025" or "APRIL 27, 2025" at start of a line
_DATE_RE = re.compile(
    r"^([A-Z][a-z]+ \d{1,2}, 202\d|[A-Z]+ \d{1,2}, 202\d)\s*$",
    re.MULTILINE | re.IGNORECASE,
)

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(raw: str) -> date | None:
    """Convert 'April 7, 2025' or 'APRIL 27, 2025' to a date object."""
    m = re.match(r"(\w+)\s+(\d{1,2}),\s+(\d{4})", raw.strip())
    if not m:
        return None
    month_name, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    month = _MONTH_MAP.get(month_name)
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


@dataclass
class ParsedWhynnEntry:
    raw_date: str
    date: date | None
    sections: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""


def split_entries(text: str) -> list[str]:
    """
    Split the full log text into individual day entry strings.
    Each chunk starts at a date header and ends before the next.
    """
    matches = list(_DATE_RE.finditer(text))
    if not matches:
        return []

    entries = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append(text[start:end])
    return entries


def parse_entry(text: str) -> ParsedWhynnEntry:
    """
    Parse a single day entry string into a ParsedWhynnEntry.
    Splits on section headers, collects raw text per section.
    """
    lines = text.splitlines()

    # First non-empty line should be the date
    raw_date = ""
    for line in lines:
        stripped = line.strip()
        if stripped:
            raw_date = stripped
            break

    parsed_date = _parse_date(raw_date)

    # Build a section header pattern
    section_pattern = re.compile(
        r"^(" + "|".join(re.escape(k) for k in SECTION_KEYS) + r")\s*:",
        re.IGNORECASE,
    )

    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        m = section_pattern.match(line.strip())
        if m:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = m.group(1).upper()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    return ParsedWhynnEntry(
        raw_date=raw_date,
        date=parsed_date,
        sections=sections,
        raw_text=text.strip(),
    )


def parse_log_file(path: str) -> list[ParsedWhynnEntry]:
    """Parse the full III_DAILY_LOGS.txt file into a list of entries."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    raw_entries = split_entries(text)
    return [parse_entry(e) for e in raw_entries]
