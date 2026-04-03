from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Any

from pydantic import BaseModel, Field


SourceType = Literal["text", "voice_transcript", "import", "manual_log", "chat_message"]
EntryType = Literal["journal", "reflection", "note"]
ActivityType = Literal[
    "workout",
    "mobility",
    "breathwork",
    "meal",
    "recovery",
    "study",
    "social",
    "work",
]
GoalStatus = Literal["active", "paused", "completed", "dropped"]
TaskStatus = Literal["todo", "in_progress", "done", "canceled"]
Priority = Literal["low", "medium", "high"]
InsightStatus = Literal["candidate", "active", "rejected", "archived", "promoted"]
HeuristicSourceType = Literal["validated_pattern", "user_defined", "correction_history"]
ProtocolStatus = Literal["active", "archived", "draft"]
CompletionStatus = Literal["completed", "partial", "skipped"]
ValueType = Literal["number", "string", "boolean"]
Provenance = Literal["user", "import", "system_extracted", "system_inferred", "system_aggregated"]
MessageRole = Literal["user", "assistant", "system"]
SearchObjectType = Literal[
    "source_document", "journal_entry", "daily_checkin", "task", "goal",
    "activity", "metric_observation",
]
PromptCycleStatus = Literal["pending", "viewed_no_response", "responded", "missed"]
EngagementEventType = Literal[
    "prompt_scheduled",
    "prompt_sent",
    "prompt_viewed_no_response",
    "prompt_responded",
    "missed_checkin",
    "streak_resumed",
    "app_open_no_entry",
    "partial_entry",
]
QuestionType = Literal["numeric", "scale", "boolean", "text", "choice"]
QuestionnaireSessionStatus = Literal["in_progress", "completed", "abandoned"]


class SourceDocumentCreate(BaseModel):
    user_id: str
    source_type: SourceType
    effective_at: datetime
    title: str | None = None
    raw_text: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class SourceDocument(BaseModel):
    id: str
    user_id: str
    source_type: SourceType
    created_at: datetime
    effective_at: datetime
    title: str | None = None
    raw_text: str
    metadata: dict = Field(default_factory=dict)
    content_hash: str


class JournalEntryCreate(BaseModel):
    user_id: str
    source_document_id: str
    effective_at: datetime
    entry_type: EntryType = "journal"
    title: str | None = None
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class JournalEntry(BaseModel):
    id: str
    user_id: str
    source_document_id: str
    created_at: datetime
    effective_at: datetime
    entry_type: EntryType
    title: str | None = None
    text: str
    tags: list[str] = Field(default_factory=list)


class DailyCheckinCreate(BaseModel):
    user_id: str
    source_document_id: str
    date: date
    effective_at: datetime
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    mood: int | None = None
    energy: int | None = None
    body_weight: float | None = None
    body_weight_unit: str | None = None
    immediate_thoughts: str | None = None
    pain_notes: str | None = None
    hydration_start: float | None = None
    hydration_unit: str | None = None
    provenance: Provenance = "user"


class DailyCheckin(BaseModel):
    id: str
    user_id: str
    source_document_id: str
    date: date
    created_at: datetime
    effective_at: datetime
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    mood: int | None = None
    energy: int | None = None
    body_weight: float | None = None
    body_weight_unit: str | None = None
    immediate_thoughts: str | None = None
    pain_notes: str | None = None
    hydration_start: float | None = None
    hydration_unit: str | None = None
    provenance: Provenance = "user"


# --- Activity ---

class ActivityCreate(BaseModel):
    user_id: str
    source_document_id: str | None = None
    effective_at: datetime
    activity_type: ActivityType
    started_at: datetime | None = None
    ended_at: datetime | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)
    provenance: Provenance = "user"
    provenance: Provenance = "user"


class Activity(BaseModel):
    id: str
    user_id: str
    source_document_id: str | None = None
    created_at: datetime
    effective_at: datetime
    activity_type: ActivityType
    started_at: datetime | None = None
    ended_at: datetime | None = None
    title: str
    description: str | None = None
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)
    provenance: Provenance = "user"


# --- MetricObservation ---

class MetricObservationCreate(BaseModel):
    user_id: str
    source_document_id: str | None = None
    effective_at: datetime
    metric_type: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str | None = None
    value_type: ValueType = "number"
    notes: str | None = None
    provenance: Provenance = "user"


class MetricObservation(BaseModel):
    id: str
    user_id: str
    source_document_id: str | None = None
    created_at: datetime
    effective_at: datetime
    metric_type: str
    value: str
    unit: str | None = None
    value_type: ValueType = "number"
    notes: str | None = None
    provenance: Provenance = "user"


# --- Protocol ---

class ProtocolCreate(BaseModel):
    user_id: str
    name: str = Field(min_length=1)
    category: str | None = None
    description: str | None = None
    steps: list[str] = Field(default_factory=list)
    target_metrics: list[str] = Field(default_factory=list)
    status: ProtocolStatus = "active"


class ProtocolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    category: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    target_metrics: list[str] | None = None
    status: ProtocolStatus | None = None


class Protocol(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    name: str
    category: str | None = None
    description: str | None = None
    steps: list[str] = Field(default_factory=list)
    target_metrics: list[str] = Field(default_factory=list)
    status: ProtocolStatus = "active"
    provenance: Provenance = "user"


# --- ProtocolExecution ---

class ProtocolExecutionCreate(BaseModel):
    user_id: str
    protocol_id: str
    source_document_id: str | None = None
    executed_at: datetime
    completion_status: CompletionStatus = "completed"
    notes: str | None = None
    provenance: Provenance = "user"


class ProtocolExecution(BaseModel):
    id: str
    user_id: str
    protocol_id: str
    source_document_id: str | None = None
    created_at: datetime
    executed_at: datetime
    completion_status: CompletionStatus = "completed"
    notes: str | None = None
    provenance: Provenance = "user"


# --- Insight ---

class InsightCreate(BaseModel):
    user_id: str
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    confidence: float | None = None
    status: InsightStatus = "candidate"
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    time_window_start: date | None = None
    time_window_end: date | None = None
    detector_key: str | None = None


class InsightUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    confidence: float | None = None
    status: InsightStatus | None = None


class Insight(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    title: str
    summary: str
    confidence: float | None = None
    status: InsightStatus = "candidate"
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    time_window_start: date | None = None
    time_window_end: date | None = None
    detector_key: str | None = None
    provenance: Provenance = "system_inferred"


# --- Heuristic ---

class HeuristicCreate(BaseModel):
    user_id: str
    rule: str = Field(min_length=1)
    source_type: HeuristicSourceType = "validated_pattern"
    confidence: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    validation_notes: str | None = None
    insight_id: str | None = None
    promotion_snapshot: dict | None = None


class Heuristic(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    rule: str
    source_type: HeuristicSourceType = "validated_pattern"
    confidence: float | None = None
    active: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    counterevidence_ids: list[str] = Field(default_factory=list)
    validation_notes: str | None = None
    insight_id: str | None = None
    promotion_snapshot: dict | None = None
    provenance: Provenance = "system_inferred"


class IngestJournalEntry(BaseModel):
    effective_at: datetime | None = None
    entry_type: EntryType = "journal"
    title: str | None = None
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class IngestCheckin(BaseModel):
    date: date
    effective_at: datetime | None = None
    sleep_hours: float | None = None
    sleep_quality: int | None = None
    mood: int | None = None
    energy: int | None = None
    body_weight: float | None = None
    body_weight_unit: str | None = None
    immediate_thoughts: str | None = None
    pain_notes: str | None = None
    hydration_start: float | None = None
    hydration_unit: str | None = None


class GoalCreate(BaseModel):
    user_id: str
    title: str = Field(min_length=1)
    description: str | None = None
    status: GoalStatus = "active"
    priority: Priority = "medium"
    target_date: date | None = None
    provenance: Provenance = "user"


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    status: GoalStatus | None = None
    priority: Priority | None = None
    target_date: date | None = None


class Goal(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    title: str
    description: str | None = None
    status: GoalStatus
    priority: Priority
    target_date: date | None = None


class TaskCreate(BaseModel):
    user_id: str
    title: str = Field(min_length=1)
    goal_id: str | None = None
    description: str | None = None
    status: TaskStatus = "todo"
    priority: Priority = "medium"
    due_at: datetime | None = None
    provenance: Provenance = "user"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    goal_id: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_at: datetime | None = None


class Task(BaseModel):
    id: str
    user_id: str
    goal_id: str | None = None
    created_at: datetime
    updated_at: datetime
    title: str
    description: str | None = None
    status: TaskStatus
    priority: Priority
    due_at: datetime | None = None
    completed_at: datetime | None = None


class PromptCycleScheduleRequest(BaseModel):
    user_id: str
    cycle_date: date
    scheduled_for: datetime
    expires_at: datetime | None = None


class PromptCycleEventRequest(BaseModel):
    user_id: str
    event_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class PromptCycleRespondRequest(PromptCycleEventRequest):
    response_source_document_id: str


class PromptCycle(BaseModel):
    id: str
    user_id: str
    cycle_date: date
    scheduled_for: datetime
    sent_at: datetime | None = None
    expires_at: datetime | None = None
    status: PromptCycleStatus
    response_source_document_id: str | None = None
    response_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EngagementEvent(BaseModel):
    id: str
    user_id: str
    prompt_cycle_id: str | None = None
    event_type: EngagementEventType
    event_at: datetime
    metadata: dict = Field(default_factory=dict)
    created_at: datetime



class EngagementSummary(BaseModel):
    user_id: str
    window_days: int
    window_start: date
    window_end: date
    total_cycles: int
    responded_cycles: int
    missed_cycles: int
    viewed_no_response_cycles: int
    pending_cycles: int
    adherence_rate: float | None = None
    avg_response_delay_minutes: float | None = None
    longest_nonresponse_streak_days: int = 0
    open_without_entry_rate: float | None = None
    streak_resume_count: int = 0


class AuditLogEntry(BaseModel):
    id: str
    user_id: str
    entity_type: str
    entity_id: str
    action: str
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    created_at: datetime
class WeeklyReviewRequest(BaseModel):
    user_id: str
    week_start: date
    week_end: date


class WeeklyReview(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    week_start: date
    week_end: date
    summary: str
    wins: list[str] = Field(default_factory=list)
    slips: list[str] = Field(default_factory=list)
    open_loops: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    engagement_notes: list[str] = Field(default_factory=list)
    insight_mentions: list[str] = Field(default_factory=list)
    activity_summary: list[str] = Field(default_factory=list)
    metric_highlights: list[str] = Field(default_factory=list)
    sparse_data_flags: list[str] = Field(default_factory=list)
    notable_entries: list[str] = Field(default_factory=list)
    llm_narrative: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None


class Conversation(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None


class ConversationMessage(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    role: MessageRole
    content: str
    created_at: datetime
    source_document_id: str | None = None


class ChatRequest(BaseModel):
    user_id: str
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ExtractionSummary(BaseModel):
    source_document_id: str
    journal_entry_id: str | None = None
    checkin_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    goal_ids: list[str] = Field(default_factory=list)
    activity_ids: list[str] = Field(default_factory=list)
    metric_ids: list[str] = Field(default_factory=list)


# Questionnaire Schema
class QuestionDef(BaseModel):
    """Definition of a single question in a questionnaire template."""
    id: str
    question_text: str
    question_type: QuestionType
    required: bool = True
    min_value: float | None = None  # For numeric/scale questions
    max_value: float | None = None  # For numeric/scale questions  
    choices: list[str] = Field(default_factory=list)  # For choice questions
    validation_regex: str | None = None  # For text questions
    help_text: str | None = None


class QuestionnaireTemplateCreate(BaseModel):
    user_id: str
    name: str
    description: str | None = None
    questions: list[QuestionDef]
    target_objects: list[str] = Field(default_factory=list)  # What data models this populates


class QuestionnaireTemplate(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    questions: list[QuestionDef]
    target_objects: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    active: bool = True


class QuestionnaireSessionCreate(BaseModel):
    user_id: str
    template_id: str
    conversation_id: str | None = None


class QuestionnaireSession(BaseModel):
    id: str
    user_id: str
    template_id: str
    conversation_id: str | None = None
    status: QuestionnaireSessionStatus
    current_question_index: int
    answers: dict[str, Any] = Field(default_factory=dict)  # question_id -> parsed_value
    raw_responses: dict[str, str] = Field(default_factory=dict)  # question_id -> raw_text
    started_at: datetime
    completed_at: datetime | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    assistant_message: str
    assistant_message_id: str
    extraction: ExtractionSummary
    memory_context: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    object_type: SearchObjectType
    object_id: str
    user_id: str
    effective_at: datetime
    title: str | None = None
    snippet: str
    source_document_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)


PromptId = Literal["open_tasks", "recent_checkins", "recent_journal", "active_goals", "attendance_this_week"]


class GuidedPrompt(BaseModel):
    id: PromptId
    label: str
    description: str
    results: list[SearchResult] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class GuidedPromptsResponse(BaseModel):
    prompts: list[GuidedPrompt] = Field(default_factory=list)


class IngestRequest(BaseModel):
    source: SourceDocumentCreate
    journal_entry: IngestJournalEntry | None = None
    checkin: IngestCheckin | None = None


class IngestResponse(BaseModel):
    source_document: SourceDocument
    journal_entry: JournalEntry | None = None
    checkin: DailyCheckin | None = None
    duplicate: bool = False












