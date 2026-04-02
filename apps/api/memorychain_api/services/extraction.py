from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from typing import Optional

from ..schemas import (
    ActivityCreate,
    DailyCheckinCreate,
    GoalCreate,
    JournalEntryCreate,
    MetricObservationCreate,
    TaskCreate,
)
from .llm import openai_client


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
    provider: str = "regex",
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
        provider: "regex" for pattern-based, "llm" for LLM-enhanced, "hybrid" for both
    """
    if provider == "llm":
        return _extract_with_llm(
            raw_text=raw_text,
            source_document_id=source_document_id,
            user_id=user_id,
            effective_at=effective_at,
            create_journal=create_journal,
            provenance=provenance,
        )
    elif provider == "hybrid":
        # Try LLM first, fall back to regex if it fails
        try:
            return _extract_with_llm(
                raw_text=raw_text,
                source_document_id=source_document_id,
                user_id=user_id,
                effective_at=effective_at,
                create_journal=create_journal,
                provenance=provenance,
            )
        except Exception:
            # Fall back to regex if LLM fails
            return _extract_with_regex(
                raw_text=raw_text,
                source_document_id=source_document_id,
                user_id=user_id,
                effective_at=effective_at,
                create_journal=create_journal,
                provenance=provenance,
            )
    else:
        # Default regex extraction
        return _extract_with_regex(
            raw_text=raw_text,
            source_document_id=source_document_id,
            user_id=user_id,
            effective_at=effective_at,
            create_journal=create_journal,
            provenance=provenance,
        )


def _extract_with_regex(
    *,
    raw_text: str,
    source_document_id: str,
    user_id: str,
    effective_at: datetime,
    create_journal: bool = True,
    provenance: str = "user",
) -> ExtractionResult:
    """Original regex-based extraction logic."""
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


def _extract_with_llm(
    *,
    raw_text: str,
    source_document_id: str,
    user_id: str,
    effective_at: datetime,
    create_journal: bool = True,
    provenance: str = "user",
) -> ExtractionResult:
    """LLM-enhanced extraction for complex text analysis."""
    
    if not openai_client:
        # No OpenAI client available, fall back to regex
        return _extract_with_regex(
            raw_text=raw_text,
            source_document_id=source_document_id,
            user_id=user_id,
            effective_at=effective_at,
            create_journal=create_journal,
            provenance=provenance,
        )
    
    # Use LLM to extract structured data
    extraction_prompt = f"""
Extract structured information from this personal log entry:

"{raw_text}"

Extract the following if present:

1. Daily Check-in Data (mood, energy, sleep hours, sleep quality, body weight - use null if not mentioned)
2. Goals (any explicit goals mentioned)  
3. Tasks/todos (any action items or things to do)
4. Activities (workouts, training, breathwork, mobility, meals, etc.)
5. Metrics (numeric measurements like weight, heart rate, strikes, etc.)

Return a JSON object with this exact structure:
{{
    "checkin": {{
        "mood": null or number 1-10,
        "energy": null or number 1-10, 
        "sleep_hours": null or number,
        "sleep_quality": null or number 1-10,
        "body_weight": null or number
    }},
    "goals": [
        {{"title": "goal text"}}
    ],
    "tasks": [
        {{"title": "task text"}}
    ],
    "activities": [
        {{
            "activity_type": "workout|mobility|breathwork|meal|recovery|study|social|work",
            "title": "activity description"
        }}
    ],
    "metrics": [
        {{
            "metric_name": "measurement name",
            "value": number,
            "unit": "unit or empty string"
        }}
    ]
}}

Be conservative - only extract data that is clearly present. Use null for missing values.
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Extract only explicitly mentioned information."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0,
            max_tokens=1000,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            if result_text.startswith("```json"):
                result_text = result_text.split("```json")[1].split("```")[0]
            elif result_text.startswith("```"):
                result_text = result_text.split("```")[1].split("```")[0]
            
            extracted_data = json.loads(result_text)
        except (json.JSONDecodeError, IndexError):
            # JSON parsing failed, fall back to regex
            return _extract_with_regex(
                raw_text=raw_text,
                source_document_id=source_document_id,
                user_id=user_id,
                effective_at=effective_at,
                create_journal=create_journal,
                provenance=provenance,
            )
        
        # Convert extracted data to schema objects
        journal = None
        if create_journal and is_substantive(raw_text):
            # Add LLM-extracted tags
            tags = ["llm_extracted"]
            if provenance == "user":
                tags.append("chat")
            elif provenance == "import":
                tags.append("import")
            
            journal = JournalEntryCreate(
                user_id=user_id,
                source_document_id=source_document_id,
                effective_at=effective_at,
                entry_type="journal",
                title="LLM-extracted entry",
                text=raw_text,
                tags=tags,
            )
        
        checkin = None
        if extracted_data.get("checkin"):
            checkin_data = extracted_data["checkin"]
            # Only create checkin if at least one field is present
            if any(checkin_data.values()):
                checkin = DailyCheckinCreate(
                    user_id=user_id,
                    source_document_id=source_document_id,
                    date=effective_at.date(),
                    effective_at=effective_at,
                    mood=checkin_data.get("mood"),
                    energy=checkin_data.get("energy"),
                    sleep_hours=checkin_data.get("sleep_hours"),
                    sleep_quality=checkin_data.get("sleep_quality"),
                    body_weight=checkin_data.get("body_weight"),
                    provenance="system_extracted",
                )
        
        goals = []
        for goal_data in extracted_data.get("goals", []):
            if goal_data.get("title"):
                goals.append(GoalCreate(
                    user_id=user_id,
                    title=goal_data["title"],
                    provenance="system_extracted",
                ))
        
        tasks = []
        for task_data in extracted_data.get("tasks", []):
            if task_data.get("title"):
                tasks.append(TaskCreate(
                    user_id=user_id, 
                    title=task_data["title"],
                    provenance="system_extracted",
                ))
        
        activities = []
        for activity_data in extracted_data.get("activities", []):
            if activity_data.get("title"):
                activities.append(ActivityCreate(
                    user_id=user_id,
                    source_document_id=source_document_id,
                    effective_at=effective_at,
                    activity_type=activity_data.get("activity_type", "workout"),
                    title=activity_data["title"],
                    provenance="system_extracted",
                ))
        
        metrics = []
        for metric_data in extracted_data.get("metrics", []):
            if metric_data.get("metric_name") and metric_data.get("value") is not None:
                metrics.append(MetricObservationCreate(
                    user_id=user_id,
                    source_document_id=source_document_id,
                    effective_at=effective_at,
                    metric_type=metric_data["metric_name"],
                    value=str(metric_data["value"]),
                    unit=metric_data.get("unit", ""),
                    provenance="system_extracted",
                ))
        
        return ExtractionResult(
            journal_entry=journal,
            checkin=checkin,
            goals=goals,
            tasks=tasks,
            activities=activities,
            metrics=metrics,
        )
        
    except Exception:
        # LLM extraction failed completely, fall back to regex
        return _extract_with_regex(
            raw_text=raw_text,
            source_document_id=source_document_id,
            user_id=user_id,
            effective_at=effective_at,
            create_journal=create_journal,
            provenance=provenance,
        )
