"""Query handler — retrieves data from the repository for query-intent messages.

When a user asks "how's my sleep been?" or "show my goals", this module
figures out what to fetch and returns structured context for the LLM reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from ..storage.repository import Repository


@dataclass
class QueryResult:
    """Structured data retrieved from the repository for a user query."""
    summary: str  # human-readable summary of what was found
    data_lines: list[str] = field(default_factory=list)  # individual data points
    object_count: int = 0


# ── Topic detection ──────────────────────────────────────────

_TOPIC_PATTERNS: dict[str, list[re.Pattern]] = {
    "sleep": [re.compile(r"\bsleep", re.I), re.compile(r"\bslept\b", re.I), re.compile(r"\brest\b", re.I)],
    "mood": [re.compile(r"\bmood", re.I), re.compile(r"\bfeel", re.I), re.compile(r"\bhappy\b", re.I)],
    "energy": [re.compile(r"\benergy", re.I), re.compile(r"\btired\b", re.I)],
    "goals": [re.compile(r"\bgoal", re.I)],
    "tasks": [re.compile(r"\btask", re.I), re.compile(r"\btodo\b", re.I), re.compile(r"\bto-do\b", re.I)],
    "insights": [re.compile(r"\binsight", re.I), re.compile(r"\bpattern", re.I), re.compile(r"\bcorrelat", re.I)],
    "heuristics": [re.compile(r"\bheuristic", re.I), re.compile(r"\brule", re.I)],
    "activities": [re.compile(r"\bactivit", re.I), re.compile(r"\bworkout", re.I), re.compile(r"\btraining\b", re.I), re.compile(r"\bexercis", re.I)],
    "checkin": [re.compile(r"\bcheck.?in", re.I), re.compile(r"\bdail", re.I)],
    "review": [re.compile(r"\breview", re.I), re.compile(r"\bweekly\b", re.I), re.compile(r"\bweek\b", re.I)],
    "metrics": [re.compile(r"\bmetric", re.I), re.compile(r"\bweight\b", re.I), re.compile(r"\bmeasur", re.I)],
}


def _detect_topics(message: str) -> list[str]:
    """Identify which data topics the user is asking about."""
    topics = []
    for topic, patterns in _TOPIC_PATTERNS.items():
        if any(p.search(message) for p in patterns):
            topics.append(topic)
    return topics or ["general"]


def _recent_date_range(message: str) -> tuple[date, date]:
    """Infer a date range from the message. Defaults to last 7 days."""
    today = date.today()

    if re.search(r"\btoday\b", message, re.I):
        return today, today
    if re.search(r"\byesterday\b", message, re.I):
        return today - timedelta(days=1), today - timedelta(days=1)
    if re.search(r"\blast\s+month\b", message, re.I):
        return today - timedelta(days=30), today
    if re.search(r"\blast\s+(?:2|two)\s+weeks?\b", message, re.I):
        return today - timedelta(days=14), today
    if re.search(r"\b(?:this|past|last)\s+week\b", message, re.I):
        return today - timedelta(days=7), today
    # Default: last 7 days
    return today - timedelta(days=7), today


# ── Topic-specific handlers ──────────────────────────────────

def _query_sleep(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    checkins = repo.list_checkins(user_id)
    relevant = [c for c in checkins if c.date and start <= c.date <= end and c.sleep_hours is not None]

    if not relevant:
        return QueryResult(summary="No sleep data found for this period.", object_count=0)

    hours = [c.sleep_hours for c in relevant]
    avg = sum(hours) / len(hours)
    lines = [f"  {c.date.isoformat()}: {c.sleep_hours}h" for c in relevant[:10]]
    return QueryResult(
        summary=f"Sleep over {len(relevant)} days: avg {avg:.1f}h, range {min(hours)}-{max(hours)}h",
        data_lines=lines,
        object_count=len(relevant),
    )


def _query_mood(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    checkins = repo.list_checkins(user_id)
    relevant = [c for c in checkins if c.date and start <= c.date <= end and c.mood is not None]

    if not relevant:
        return QueryResult(summary="No mood data found for this period.", object_count=0)

    moods = [c.mood for c in relevant]
    avg = sum(moods) / len(moods)
    lines = [f"  {c.date.isoformat()}: mood {c.mood}/10" for c in relevant[:10]]
    return QueryResult(
        summary=f"Mood over {len(relevant)} days: avg {avg:.1f}/10, range {min(moods)}-{max(moods)}",
        data_lines=lines,
        object_count=len(relevant),
    )


def _query_energy(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    checkins = repo.list_checkins(user_id)
    relevant = [c for c in checkins if c.date and start <= c.date <= end and c.energy is not None]

    if not relevant:
        return QueryResult(summary="No energy data found for this period.", object_count=0)

    energy = [c.energy for c in relevant]
    avg = sum(energy) / len(energy)
    lines = [f"  {c.date.isoformat()}: energy {c.energy}/10" for c in relevant[:10]]
    return QueryResult(
        summary=f"Energy over {len(relevant)} days: avg {avg:.1f}/10, range {min(energy)}-{max(energy)}",
        data_lines=lines,
        object_count=len(relevant),
    )


def _query_goals(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    goals = repo.list_goals(user_id=user_id, limit=20)
    active = [g for g in goals if g.status == "active"]

    if not active:
        return QueryResult(summary="No active goals.", object_count=0)

    lines = [f"  • {g.title} (since {g.created_at[:10] if isinstance(g.created_at, str) else ''})" for g in active]
    return QueryResult(
        summary=f"{len(active)} active goal(s)",
        data_lines=lines,
        object_count=len(active),
    )


def _query_tasks(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    tasks = repo.list_tasks(user_id=user_id, limit=50)
    open_tasks = [t for t in tasks if t.status not in ("completed", "cancelled")]

    if not open_tasks:
        return QueryResult(summary="No open tasks.", object_count=0)

    lines = [f"  • [{t.status}] {t.title}" for t in open_tasks[:15]]
    return QueryResult(
        summary=f"{len(open_tasks)} open task(s)",
        data_lines=lines,
        object_count=len(open_tasks),
    )


def _query_insights(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    insights = repo.list_insights(user_id=user_id, limit=20)

    if not insights:
        return QueryResult(summary="No insights found.", object_count=0)

    lines = []
    for ins in insights[:10]:
        conf = f" (confidence: {ins.confidence:.2f})" if ins.confidence else ""
        lines.append(f"  • [{ins.status}] {ins.title}{conf}")
    return QueryResult(
        summary=f"{len(insights)} insight(s) — {sum(1 for i in insights if i.status == 'candidate')} candidates, {sum(1 for i in insights if i.status == 'active')} active",
        data_lines=lines,
        object_count=len(insights),
    )


def _query_heuristics(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    heuristics = repo.list_heuristics(user_id=user_id, limit=20)
    active = [h for h in heuristics if h.is_active]

    if not active:
        return QueryResult(summary="No active heuristics.", object_count=0)

    lines = [f"  • {h.rule_text[:80]}" for h in active]
    return QueryResult(
        summary=f"{len(active)} active heuristic(s)",
        data_lines=lines,
        object_count=len(active),
    )


def _query_activities(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    activities = repo.list_activities(user_id=user_id, limit=50)
    # Filter by date range if created_at is available
    lines = [f"  • {a.activity_type}: {a.title}" for a in activities[:15]]

    if not activities:
        return QueryResult(summary="No activities recorded.", object_count=0)

    return QueryResult(
        summary=f"{len(activities)} activit(ies) recorded",
        data_lines=lines,
        object_count=len(activities),
    )


def _query_checkin(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    checkins = repo.list_checkins(user_id)
    relevant = [c for c in checkins if c.date and start <= c.date <= end]

    if not relevant:
        return QueryResult(summary="No check-ins found for this period.", object_count=0)

    lines = []
    for c in relevant[:10]:
        parts = []
        if c.sleep_hours is not None:
            parts.append(f"sleep {c.sleep_hours}h")
        if c.mood is not None:
            parts.append(f"mood {c.mood}/10")
        if c.energy is not None:
            parts.append(f"energy {c.energy}/10")
        lines.append(f"  {c.date.isoformat()}: {', '.join(parts) or 'no metrics'}")

    return QueryResult(
        summary=f"{len(relevant)} check-in(s) from {start} to {end}",
        data_lines=lines,
        object_count=len(relevant),
    )


def _query_general(repo: Repository, user_id: str, start: date, end: date) -> QueryResult:
    """Broad overview when no specific topic detected."""
    checkins = repo.list_checkins(user_id)
    goals = repo.list_goals(user_id=user_id, limit=5)
    tasks = repo.list_tasks(user_id=user_id, limit=5)
    insights = repo.list_insights(user_id=user_id, limit=5)

    recent = [c for c in checkins if c.date and start <= c.date <= end]
    active_goals = [g for g in goals if g.status == "active"]
    open_tasks = [t for t in tasks if t.status not in ("completed", "cancelled")]

    lines = [
        f"  Check-ins (last 7d): {len(recent)}",
        f"  Active goals: {len(active_goals)}",
        f"  Open tasks: {len(open_tasks)}",
        f"  Insights: {len(insights)}",
    ]

    return QueryResult(
        summary="Here's your current overview:",
        data_lines=lines,
        object_count=len(recent) + len(active_goals) + len(open_tasks),
    )


_TOPIC_HANDLERS = {
    "sleep": _query_sleep,
    "mood": _query_mood,
    "energy": _query_energy,
    "goals": _query_goals,
    "tasks": _query_tasks,
    "insights": _query_insights,
    "heuristics": _query_heuristics,
    "activities": _query_activities,
    "checkin": _query_checkin,
    "review": _query_checkin,  # show checkin data for "weekly" queries
    "metrics": _query_activities,  # close enough for now
    "general": _query_general,
}


def handle_query(repo: Repository, user_id: str, message: str) -> list[QueryResult]:
    """Execute a data query and return structured results.

    Detects what topics the user is asking about, fetches relevant data
    from the repository, and returns formatted results.
    """
    topics = _detect_topics(message)
    start, end = _recent_date_range(message)
    results = []

    for topic in topics:
        handler = _TOPIC_HANDLERS.get(topic, _query_general)
        result = handler(repo, user_id, start, end)
        results.append(result)

    return results
