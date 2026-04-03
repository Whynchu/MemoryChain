"""Insight detection engine.

Each detector is a standalone function that takes a Repository and user_id,
analyzes the data, and returns a newly created Insight or None.

Detectors are statistically grounded — they use real correlation coefficients,
not arbitrary bucket comparisons.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from math import sqrt

from ..schemas import Insight, InsightCreate
from ..storage.repository import Repository

DETECTOR_KEY_SLEEP_MOOD = "sleep_mood_v1"

# Minimum data points for a meaningful correlation
MIN_DATA_POINTS = 7

# Minimum |r| to consider a correlation worth reporting
MIN_CORRELATION = 0.3


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient between two equal-length lists."""
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (n - 1)
    std_x = statistics.stdev(xs)
    std_y = statistics.stdev(ys)
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)


def _r_to_confidence(r: float) -> float:
    """Map |r| to a 0.0–1.0 confidence score."""
    abs_r = abs(r)
    if abs_r < 0.3:
        return 0.0
    if abs_r < 0.5:
        # 0.3–0.5 → confidence 0.4–0.6
        return 0.4 + (abs_r - 0.3) * (0.2 / 0.2)
    if abs_r < 0.7:
        # 0.5–0.7 → confidence 0.6–0.8
        return 0.6 + (abs_r - 0.5) * (0.2 / 0.2)
    # 0.7–1.0 → confidence 0.8–0.95
    return min(0.8 + (abs_r - 0.7) * (0.15 / 0.3), 0.95)


def detect_sleep_mood(
    repo: Repository,
    user_id: str,
    lookback_days: int = 60,
) -> Insight | None:
    """Detect correlation between sleep duration and mood.

    Uses Pearson correlation for detection, then computes descriptive
    group stats (median split) for the human-readable summary.

    Returns the newly created Insight, or None if no meaningful
    correlation found or if an existing insight already covers this.
    """
    # Check for existing insight (dedup + rejection blocking)
    existing = repo.list_insights(user_id=user_id, status=None)
    for ins in existing:
        if ins.detector_key == DETECTOR_KEY_SLEEP_MOOD:
            if ins.status in ("rejected",):
                return None  # Respect user's judgment
            if ins.status in ("candidate", "active", "promoted"):
                return None  # Already exists, don't duplicate

    # Gather data
    checkins = repo.list_checkins(user_id)
    cutoff = date.today() - timedelta(days=lookback_days)

    # Filter to checkins with both fields and within window
    data = []
    for c in checkins:
        if c.sleep_hours is not None and c.mood is not None and c.date >= cutoff:
            data.append(c)

    if len(data) < MIN_DATA_POINTS:
        return None

    sleep_vals = [c.sleep_hours for c in data]
    mood_vals = [float(c.mood) for c in data]

    # Compute correlation
    r = _pearson(sleep_vals, mood_vals)
    if abs(r) < MIN_CORRELATION:
        return None

    confidence = _r_to_confidence(r)

    # Descriptive group stats for the summary (split at median)
    median_sleep = statistics.median(sleep_vals)
    low_group = [m for s, m in zip(sleep_vals, mood_vals) if s < median_sleep]
    high_group = [m for s, m in zip(sleep_vals, mood_vals) if s >= median_sleep]

    low_avg = statistics.mean(low_group) if low_group else 0
    high_avg = statistics.mean(high_group) if high_group else 0

    # Time window
    dates = sorted(c.date for c in data)
    window_start = dates[0]
    window_end = dates[-1]

    direction = "positively" if r > 0 else "negatively"
    strength = "strongly" if abs(r) >= 0.7 else "moderately" if abs(r) >= 0.5 else "weakly"
    summary = (
        f"Your sleep and mood are {strength} {direction} correlated (r={r:.2f}). "
        f"On days with <{median_sleep:.1f}h sleep, mood averaged {low_avg:.1f}/10 "
        f"vs {high_avg:.1f}/10 on days with ≥{median_sleep:.1f}h "
        f"(n={len(data)}, {(window_end - window_start).days}-day window)."
    )

    evidence_ids = [c.id for c in data]

    payload = InsightCreate(
        user_id=user_id,
        title="Sleep duration correlates with mood",
        summary=summary,
        confidence=round(confidence, 2),
        status="candidate",
        evidence_ids=evidence_ids,
        counterevidence_ids=[],
        time_window_start=window_start,
        time_window_end=window_end,
        detector_key=DETECTOR_KEY_SLEEP_MOOD,
    )

    return repo.create_insight(payload)


# -- Detector registry --

_DETECTORS = [
    detect_sleep_mood,
]


def run_all_detectors(repo: Repository, user_id: str) -> list[Insight]:
    """Run all registered detectors and return newly created insights."""
    results = []
    for detector in _DETECTORS:
        insight = detector(repo, user_id)
        if insight is not None:
            results.append(insight)
    return results
