from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re

from ..schemas import (
    ActivityCreate,
    DailyCheckinCreate,
    GoalCreate,
    JournalEntryCreate,
    MetricObservationCreate,
    TaskCreate,
)


@dataclass
class ExtractionResult:
    """All objects extracted from a single piece of text."""
    journal_entry: JournalEntryCreate | None = None
    checkin: DailyCheckinCreate | None = None
    goals: list[GoalCreate] = field(default_factory=list)
    tasks: list[TaskCreate] = field(default_factory=list)
    activities: list[ActivityCreate] = field(default_factory=list)
    metrics: list[MetricObservationCreate] = field(default_factory=list)


def _extract_goals(user_id: str, text: str) -> list[GoalCreate]:
    goals: list[GoalCreate] = []
    for match in re.finditer(r"(?is)\bgoal\s*:\s*(.+?)(?=(?:\b(?:todo|goal)\s*:)|$)", text):
        title = match.group(1).strip().rstrip(".,;:! ")
        if title:
            goals.append(GoalCreate(user_id=user_id, title=title))
    return goals


def _extract_tasks(user_id: str, text: str) -> list[TaskCreate]:
    tasks: list[TaskCreate] = []
    for match in re.finditer(r"(?is)\btodo\s*:\s*(.+?)(?=(?:\b(?:todo|goal)\s*:)|$)", text):
        title = match.group(1).strip().rstrip(".,;:! ")
        if title:
            tasks.append(TaskCreate(user_id=user_id, title=title))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            title = stripped[5:].strip()
            if title:
                tasks.append(TaskCreate(user_id=user_id, title=title))
    return tasks


def _extract_checkin(
    *,
    user_id: str,
    source_document_id: str,
    text: str,
    effective_at: datetime,
) -> DailyCheckinCreate | None:
    sleep_match = re.search(r"sleep\s+(\d+(?:\.\d+)?)\s*h", text, flags=re.IGNORECASE)
    mood_match = re.search(r"mood\s+(\d{1,2})\s*/\s*10", text, flags=re.IGNORECASE)
    energy_match = re.search(r"energy\s+(\d{1,2})\s*/\s*10", text, flags=re.IGNORECASE)

    if not (sleep_match or mood_match or energy_match):
        return None

    return DailyCheckinCreate(
        user_id=user_id,
        source_document_id=source_document_id,
        date=effective_at.date(),
        effective_at=effective_at,
        sleep_hours=float(sleep_match.group(1)) if sleep_match else None,
        mood=int(mood_match.group(1)) if mood_match else None,
        energy=int(energy_match.group(1)) if energy_match else None,
    )


def _extract_activities(
    *,
    user_id: str,
    source_document_id: str,
    text: str,
    effective_at: datetime,
) -> list[ActivityCreate]:
    """Extract activity mentions from text."""
    activities: list[ActivityCreate] = []
    workout_match = re.search(
        r"(?i)(?:did|completed|finished)\s+(?:a\s+)?(\d+)\s*(?:min(?:ute)?s?|hr?s?)\s+(?:of\s+)?(\w[\w\s]{2,30}?)(?:\.|,|$)",
        text,
    )
    if workout_match:
        title = workout_match.group(2).strip()
        activities.append(
            ActivityCreate(
                user_id=user_id,
                source_document_id=source_document_id,
                effective_at=effective_at,
                activity_type="workout",
                title=title,
                provenance="system_extracted",
            )
        )
    # Simple keyword patterns for activity types
    activity_patterns = [
        (r"(?i)\b(?:workout|training|sparring|bagwork|padwork|lifting|gym)\b", "workout"),
        (r"(?i)\b(?:stretch(?:ing)?|mobility|yoga|foam roll)\b", "mobility"),
        (r"(?i)\b(?:breathwork|breathing|wim hof|co2)\b", "breathwork"),
        (r"(?i)\b(?:meditat(?:ion|ed)|mindful)\b", "recovery"),
    ]
    for pattern, activity_type in activity_patterns:
        if re.search(pattern, text) and not activities:
            activities.append(
                ActivityCreate(
                    user_id=user_id,
                    source_document_id=source_document_id,
                    effective_at=effective_at,
                    activity_type=activity_type,
                    title=f"{activity_type.title()} session",
                    provenance="system_extracted",
                )
            )
            break
    return activities


def _extract_metrics(
    *,
    user_id: str,
    source_document_id: str,
    text: str,
    effective_at: datetime,
) -> list[MetricObservationCreate]:
    """Extract metric observations from text."""
    metrics: list[MetricObservationCreate] = []
    patterns = [
        (r"(?i)(?:body\s*)?weight\s*[:\s]+(\d+(?:\.\d+)?)\s*(lbs?|kg|pounds?)?", "body_weight"),
        (r"(?i)heart\s*rate\s*[:\s]+(\d+)\s*(bpm)?", "heart_rate"),
        (r"(?i)(?:total\s+)?(?:hydration|water)\s*[:\s]+~?(\d+(?:\.\d+)?)\s*(oz|ml|L)?", "hydration"),
        (r"(?i)co2\s*hold\s*[:\s]+~?(\d+(?:\.\d+)?)\s*(s(?:ec(?:ond)?s?)?|min)?", "co2_hold"),
        (r"(?i)(?:total\s+)?strikes?\s*[:\s]+(\d+)", "total_strikes"),
    ]
    for pattern, metric_type in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            metrics.append(
                MetricObservationCreate(
                    user_id=user_id,
                    source_document_id=source_document_id,
                    effective_at=effective_at,
                    metric_type=metric_type,
                    value=value,
                    unit=unit,
                    provenance="system_extracted",
                )
            )
    return metrics


# Minimum length for a chat message to be considered "substantive" enough for a journal entry
_MIN_SUBSTANTIVE_LENGTH = 40
_SUBSTANTIVE_PATTERNS = re.compile(
    r"(?i)(?:sleep|mood|energy|todo:|goal:|journal:|reflect|felt|feeling|dream|woke|train(?:ing|ed))"
)


def is_substantive(text: str) -> bool:
    """Return True if the text is substantive enough to warrant a JournalEntry."""
    if len(text.strip()) >= _MIN_SUBSTANTIVE_LENGTH:
        return True
    if _SUBSTANTIVE_PATTERNS.search(text):
        return True
    return False


def extract_objects(
    *,
    raw_text: str,
    source_document_id: str,
    user_id: str,
    effective_at: datetime,
    create_journal: bool = True,
    provenance: str = "user",
) -> ExtractionResult:
    """
    Run all extraction logic on a piece of text.

    Args:
        raw_text: The raw input text to extract from.
        source_document_id: ID of the source document this came from.
        user_id: The user who owns this data.
        effective_at: When the content was authored.
        create_journal: Whether to create a JournalEntry (False for non-substantive chat).
        provenance: Origin of the data.
    """
    journal = None
    if create_journal and is_substantive(raw_text):
        journal = JournalEntryCreate(
            user_id=user_id,
            source_document_id=source_document_id,
            effective_at=effective_at,
            entry_type="journal",
            title="Chat capture" if provenance == "user" else "Imported entry",
            text=raw_text,
            tags=["chat"] if provenance == "user" else ["import"],
        )

    checkin = _extract_checkin(
        user_id=user_id,
        source_document_id=source_document_id,
        text=raw_text,
        effective_at=effective_at,
    )

    goals = _extract_goals(user_id, raw_text)
    tasks = _extract_tasks(user_id, raw_text)
    activities = _extract_activities(
        user_id=user_id,
        source_document_id=source_document_id,
        text=raw_text,
        effective_at=effective_at,
    )
    metrics = _extract_metrics(
        user_id=user_id,
        source_document_id=source_document_id,
        text=raw_text,
        effective_at=effective_at,
    )

    return ExtractionResult(
        journal_entry=journal,
        checkin=checkin,
        goals=goals,
        tasks=tasks,
        activities=activities,
        metrics=metrics,
    )
