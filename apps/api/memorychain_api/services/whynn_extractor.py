"""
WHYNN log field extractors.

Deterministic regex-based extraction for each section type.
Handles: approximate values (~140), ranges (7-8), [Not recorded],
unit variance, and encoding artifacts (CO? for CO₂).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Matches a leading [Not recorded] / [Not ...] / [anything in brackets that
# isn't a plain number we might want], or descriptive text-only values.
_NOT_RECORDED_RE = re.compile(
    r"^\[(?!~?[\d])[^\]]*\]$|"       # bracket value without a leading number
    r"^\[(?!~?[\d])[^\]]*",           # bracket value that continues past bracket
    re.IGNORECASE,
)

def _is_not_recorded(value: str) -> bool:
    """Return True if the value represents 'not recorded' or pure descriptive text."""
    v = value.strip()
    if not v:
        return True
    # Bracket values: [Not recorded], [Data captured elsewhere], [Pending ...]
    if v.startswith("["):
        # Allow values like "[~402]" that contain a number
        inner = v.lstrip("[").rstrip("]")
        if not re.search(r"[\d]", inner):
            return True
    # Pure alphabetic descriptions (no digits at all)
    if not re.search(r"[\d]", v):
        return True
    return False


def _is_bracket_not_recorded(value: str) -> bool:
    """
    Return True only for explicit [Not recorded]-style bracket values.
    Use this for free-text fields where descriptive text is valid.
    """
    v = value.strip()
    if not v:
        return True
    if v.startswith("["):
        inner = v.lstrip("[").rstrip("]").lower()
        # Common markers
        if any(k in inner for k in ["not recorded", "not entered", "not noted", "pending", "captured", "logged separately"]):
            return True
        # Bracket with no numeric content = likely a note, not a value
        if not re.search(r"[\d]", inner):
            return True
    return False


def _extract_first_float(text: str) -> Optional[float]:
    """Extract the first numeric float from a string."""
    m = re.search(r"~?(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _extract_range_avg(text: str) -> Optional[float]:
    """
    Extract a numeric value from patterns like '7/10', '7-8', '7–8/10',
    '6–7 / 10', '7 / 10'. Returns the lower bound of a range.
    """
    # Normalise unicode dash/minus to ASCII hyphen
    text = text.replace("–", "-").replace("—", "-").replace("→", "-")
    # Remove trailing context in parens: "8/10 (note)" → "8/10"
    text = re.sub(r"\(.*", "", text).strip()

    # X/Y or X / Y  (scale out of 10)
    m = re.match(r"~?(\d+(?:\.\d+)?)\s*/\s*\d+", text)
    if m:
        return float(m.group(1))

    # X-Y range (take lower bound)
    m = re.match(r"~?(\d+(?:\.\d+)?)\s*[-–]\s*\d+", text)
    if m:
        return float(m.group(1))

    # Plain number
    m = re.match(r"~?(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))

    return None


# ---------------------------------------------------------------------------
# Extracted data containers
# ---------------------------------------------------------------------------

@dataclass
class SystemMetrics:
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[float] = None
    mood: Optional[float] = None
    energy: Optional[float] = None
    body_weight_lbs: Optional[float] = None
    wakeup_time: Optional[str] = None
    immediate_thoughts: Optional[str] = None


@dataclass
class BreathworkMetrics:
    co2_hold_seconds: Optional[float] = None


@dataclass
class TrainingData:
    session_type: Optional[str] = None
    total_strikes: Optional[int] = None
    duration_minutes: Optional[float] = None
    distance_km: Optional[float] = None
    avg_hr_bpm: Optional[int] = None
    max_hr_bpm: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class NutritionData:
    hydration_oz: Optional[float] = None


@dataclass
class ExtractedWhynnEntry:
    system: SystemMetrics = field(default_factory=SystemMetrics)
    breathwork: BreathworkMetrics = field(default_factory=BreathworkMetrics)
    training: TrainingData = field(default_factory=TrainingData)
    nutrition: NutritionData = field(default_factory=NutritionData)
    buffs: list[str] = field(default_factory=list)
    xp_total: Optional[int] = None
    system_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def _field_value(section_text: str, field_name: str) -> Optional[str]:
    """
    Pull the value after 'Field Name:' from a section block.
    Returns None if not found or if the value is a [Not recorded] marker.
    Use for numeric/quantitative fields.
    """
    pattern = re.compile(
        r"(?:^|[\n\r])[^:\n]*?" + re.escape(field_name) + r"\s*:\s*(.+)",
        re.IGNORECASE,
    )
    m = pattern.search(section_text)
    if not m:
        return None
    value = m.group(1).strip()
    if _is_not_recorded(value):
        return None
    return value


def _field_text_value(section_text: str, field_name: str) -> Optional[str]:
    """
    Pull the value after 'Field Name:' from a section block.
    Returns None only for explicit [Not recorded]-style brackets.
    Use for free-text fields where descriptive values are valid.
    """
    pattern = re.compile(
        r"(?:^|[\n\r])[^:\n]*?" + re.escape(field_name) + r"\s*:\s*(.+)",
        re.IGNORECASE,
    )
    m = pattern.search(section_text)
    if not m:
        return None
    value = m.group(1).strip()
    if _is_bracket_not_recorded(value):
        return None
    return value


def extract_system_metrics(section_text: str) -> SystemMetrics:
    result = SystemMetrics()

    # Sleep hours: "~7 hours", "7–8 hrs", "7 hrs 10 min", "8 hours (5 core + 3 hr nap)"
    sleep_raw = _field_value(section_text, "Total Sleep")
    if sleep_raw:
        # Normalise dashes
        sleep_raw = sleep_raw.replace("–", "-").replace("—", "-")
        # "7 hrs 10 min" → convert minutes
        m = re.match(r"~?(\d+(?:\.\d+)?)\s*h[^\d]*(\d+)\s*min", sleep_raw, re.IGNORECASE)
        if m:
            result.sleep_hours = float(m.group(1)) + float(m.group(2)) / 60
        else:
            result.sleep_hours = _extract_range_avg(sleep_raw)

    # Sleep quality: "7/10", "8–9", "8/10 – Solid sleep"
    sq_raw = _field_value(section_text, "Sleep Quality")
    if sq_raw:
        result.sleep_quality = _extract_range_avg(sq_raw)

    # Mood: "7/10", "6–7/10", "8/10 (excited)"
    # Also handles "Morning Mood: 8/10"
    mood_raw = _field_value(section_text, "Mood") or _field_value(section_text, "Morning Mood")
    if mood_raw:
        # If it looks like descriptive text (no digit/slash), skip
        result.mood = _extract_range_avg(mood_raw)

    # Energy: "8/10", "7–8/10", "Morning Energy: 8/10"
    energy_raw = _field_value(section_text, "Energy") or _field_value(section_text, "Morning Energy")
    if energy_raw:
        result.energy = _extract_range_avg(energy_raw)

    # Body weight — multiple patterns:
    # "~137.2 lbs (estimated AM)", "138.1 lbs", "[Recorded PM at 136.5 lbs]"
    # "138.9 lbs → 138.2 lbs" — take first, "141.2 lbs (post-bathroom)"
    bw_raw = _field_value(section_text, "Morning Body Weight")
    if bw_raw is None:
        # Try bracket form: [Recorded PM at 136.5 lbs]
        m = re.search(r"Morning Body Weight\s*:\s*\[Recorded (?:PM|AM) at (~?\d+\.?\d*)\s*lbs?\]", section_text, re.IGNORECASE)
        if m:
            bw_raw = m.group(1) + " lbs"
    if bw_raw:
        # Remove arrow notation, take first number
        bw_raw = re.sub(r"→.*", "", bw_raw)
        result.body_weight_lbs = _extract_first_float(bw_raw)

    # Wakeup time (keep as string)
    wakeup_raw = _field_text_value(section_text, "Wakeup Time")
    if wakeup_raw:
        result.wakeup_time = wakeup_raw.strip()

    # Immediate thoughts
    it_raw = _field_text_value(section_text, "Immediate Thoughts")
    if it_raw:
        result.immediate_thoughts = it_raw.strip()

    return result


def extract_breathwork_metrics(section_text: str) -> BreathworkMetrics:
    result = BreathworkMetrics()

    # CO₂ hold — encoded as "CO? Hold" in file due to encoding artifact
    # Patterns: "Max 31.22 seconds", "19.16 seconds (Standing Test)", "43.15 seconds"
    # Also "Max CO? Hold:" as an alternate field name
    for field_name in ["CO? Hold", "CO2 Hold", "Max CO? Hold", "Standing CO? Hold"]:
        raw = _field_value(section_text, field_name)
        if raw:
            m = re.search(r"(\d+(?:\.\d+)?)\s*sec", raw, re.IGNORECASE)
            if m:
                result.co2_hold_seconds = float(m.group(1))
                break

    return result


def extract_training(section_text: str) -> TrainingData:
    result = TrainingData()

    # Session type
    type_raw = _field_text_value(section_text, "Training Session Type")
    if type_raw:
        result.session_type = type_raw.strip()

    # Total strikes — may appear inline in session notes
    # "Total Strikes: 488", "[~402]"
    strikes_raw = _field_value(section_text, "Total Strikes")
    if strikes_raw:
        # Handle [~402]
        m = re.search(r"~?(\d+)", strikes_raw)
        if m:
            result.total_strikes = int(m.group(1))

    # Duration — "57 min total", "45:26", "Duration: 45:26"
    dur_raw = _field_value(section_text, "Duration")
    if dur_raw:
        # "HH:MM:SS" or "MM:SS" format
        colon_m = re.match(r"(\d+):(\d{2})(?::(\d{2}))?", dur_raw.strip())
        if colon_m:
            h_or_m = int(colon_m.group(1))
            seconds = int(colon_m.group(2))
            extra = int(colon_m.group(3) or 0)
            if extra:  # H:MM:SS
                result.duration_minutes = h_or_m * 60 + seconds + extra / 60
            else:  # MM:SS
                result.duration_minutes = h_or_m + seconds / 60
        else:
            # "57 min total"
            min_m = re.search(r"(\d+)\s*min", dur_raw, re.IGNORECASE)
            if min_m:
                result.duration_minutes = float(min_m.group(1))
    else:
        # Try to find "X min total" inline in the section
        m = re.search(r"(\d+)\s+min\s+total", section_text, re.IGNORECASE)
        if m:
            result.duration_minutes = float(m.group(1))

    # Distance
    dist_raw = _field_value(section_text, "Distance")
    if dist_raw:
        m = re.search(r"(\d+(?:\.\d+)?)\s*km", dist_raw, re.IGNORECASE)
        if m:
            result.distance_km = float(m.group(1))
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*mi", dist_raw, re.IGNORECASE)
            if m:
                result.distance_km = round(float(m.group(1)) * 1.60934, 2)

    # Average HR
    avg_hr_raw = _field_value(section_text, "Average HR")
    if avg_hr_raw:
        m = re.search(r"~?(\d+)", avg_hr_raw)
        if m:
            result.avg_hr_bpm = int(m.group(1))

    # Max HR
    max_hr_raw = _field_value(section_text, "Max HR")
    if max_hr_raw:
        m = re.search(r"(\d+)", max_hr_raw)
        if m:
            result.max_hr_bpm = int(m.group(1))

    # Session notes (freeform)
    notes_raw = _field_text_value(section_text, "Session Notes")
    if notes_raw:
        result.notes = notes_raw.strip()

    return result


def extract_nutrition(section_text: str) -> NutritionData:
    result = NutritionData()

    # Hydration: "~140 oz water + IV", "~135+ oz", "128 oz", "~138–140 oz"
    hyd_raw = _field_value(section_text, "Total Hydration")
    if hyd_raw:
        # Normalise dashes
        hyd_raw = hyd_raw.replace("–", "-").replace("—", "-")
        # Strip "+": "135+" → "135"
        hyd_raw = hyd_raw.replace("+", "")
        result.hydration_oz = _extract_first_float(hyd_raw)

    return result


def extract_buffs(section_text: str) -> list[str]:
    """Extract buff names from the BUFFS TRIGGERED section."""
    buffs = []
    for line in section_text.splitlines():
        line = line.strip()
        # Lines start with bullet chars like "•", "–", unicode bullets
        # After stripping leading bullet/whitespace we get the buff name
        line = re.sub(r"^[•\-–—??\s]+", "", line).strip()
        if line:
            buffs.append(line)
    return buffs


def extract_xp_total(section_text: str) -> Optional[int]:
    """Extract total XP from the XP AWARDS section."""
    m = re.search(r"TOTAL XP GAINED\s*:\s*\+?(\d+)\s*XP", section_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_table_format_metrics(raw_text: str, result: "ExtractedWhynnEntry") -> None:
    """
    Fallback extractor for May-style table format entries.
    These use 'MetricValue\nFieldNameValue' layout (no colons for system metrics),
    but colon-format for training stats.

    Handles patterns like:
      Sleep~7.5 hrs (21:00–04:40)
      Sleep Quality8 / 10
      Mood (Wake → Drive)7 → 5
      Energy on Wake8
      Weight (Post-Output → Post-Stack)141.8 → 142.2 lbs
    """
    # Sleep: "Sleep~7.5 hrs" or "Sleep Duration\t~6.5 hrs" (tab-separated format)
    if result.system.sleep_hours is None:
        m = re.search(r"Sleep[^0-9\n]{0,25}(~?\d+(?:\.\d+)?)\s*hrs?", raw_text, re.IGNORECASE)
        if m:
            result.system.sleep_hours = float(m.group(1).lstrip("~"))

    # Sleep quality: "Sleep Quality8 / 10"
    if result.system.sleep_quality is None:
        m = re.search(r"Sleep Quality\s*(\d+)\s*/\s*10", raw_text, re.IGNORECASE)
        if m:
            result.system.sleep_quality = float(m.group(1))

    # Mood: "Mood (Wake → Drive)7 → 5" — take first number
    if result.system.mood is None:
        m = re.search(r"Mood[^0-9\n]{0,30}(\d+)", raw_text, re.IGNORECASE)
        if m:
            result.system.mood = float(m.group(1))

    # Energy: "Energy on Wake8"
    if result.system.energy is None:
        m = re.search(r"Energy[^0-9\n]{0,20}(\d+)", raw_text, re.IGNORECASE)
        if m:
            result.system.energy = float(m.group(1))

    # Weight: "Weight (Post-Output → Post-Stack)\t141.8 → 142.2 lbs"
    # The → may be encoded as '?' in the file, so avoid strict lookahead
    if result.system.body_weight_lbs is None:
        m = re.search(r"Weight[^0-9\n]{0,50}(~?1[2-5]\d(?:\.\d+)?)", raw_text, re.IGNORECASE)
        if m:
            result.system.body_weight_lbs = float(m.group(1).lstrip("~"))

    # CO₂ hold: "CO? Hold AM35.47 sec"
    if result.breathwork.co2_hold_seconds is None:
        m = re.search(r"CO.?\s*Hold[^0-9\n]{0,15}(\d+(?:\.\d+)?)\s*sec", raw_text, re.IGNORECASE)
        if m:
            result.breathwork.co2_hold_seconds = float(m.group(1))

    # Total strikes (still colon-format even in table entries)
    # Also handle inline format: "6 Rounds / 433 Strikes"
    if result.training.total_strikes is None:
        m = re.search(r"Total Strikes\s*:\s*\[?~?(\d+)\]?", raw_text, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d{3,})\s+Strikes\b", raw_text, re.IGNORECASE)
        if m:
            result.training.total_strikes = int(m.group(1))

    # Hydration: "Daily Hydration Total160 oz" or "Total Hydration: 160 oz"
    if result.nutrition.hydration_oz is None:
        m = re.search(r"(?:Daily\s+)?Hydration\s+Total\s*[:\s]\s*~?(\d+(?:\.\d+)?)\s*oz", raw_text, re.IGNORECASE)
        if m:
            result.nutrition.hydration_oz = float(m.group(1))

    # Average HR (colon format still used in training modules)
    if result.training.avg_hr_bpm is None:
        m = re.search(r"(?:AVG|Average)\s+HR\s*:\s*~?(\d+)", raw_text, re.IGNORECASE)
        if m:
            result.training.avg_hr_bpm = int(m.group(1))

    # Max HR
    if result.training.max_hr_bpm is None:
        m = re.search(r"Max\s+HR\s*:\s*(\d+)", raw_text, re.IGNORECASE)
        if m:
            result.training.max_hr_bpm = int(m.group(1))


def extract_entry(parsed_entry) -> ExtractedWhynnEntry:
    """
    Run all extractors against a ParsedWhynnEntry's sections.
    Falls back to full-text extraction for table-format (May-style) entries.
    Returns an ExtractedWhynnEntry with all fields populated.
    """
    sections = parsed_entry.sections
    result = ExtractedWhynnEntry()

    if "SYSTEM METRICS" in sections:
        result.system = extract_system_metrics(sections["SYSTEM METRICS"])

    if "BREATHWORK & PHYSICAL METRICS" in sections:
        result.breathwork = extract_breathwork_metrics(sections["BREATHWORK & PHYSICAL METRICS"])

    if "TRAINING EXECUTION" in sections:
        result.training = extract_training(sections["TRAINING EXECUTION"])

    if "NUTRITION & HYDRATION" in sections:
        result.nutrition = extract_nutrition(sections["NUTRITION & HYDRATION"])

    if "BUFFS TRIGGERED" in sections:
        result.buffs = extract_buffs(sections["BUFFS TRIGGERED"])

    if "XP AWARDS" in sections:
        result.xp_total = extract_xp_total(sections["XP AWARDS"])

    if "SYSTEM NOTES" in sections:
        result.system_notes = sections["SYSTEM NOTES"].strip() or None

    # Fallback: if few/no sections found, try table-format extraction on full text
    if len(sections) < 3 and parsed_entry.raw_text:
        _extract_table_format_metrics(parsed_entry.raw_text, result)

    return result
