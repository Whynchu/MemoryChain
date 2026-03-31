from __future__ import annotations

from datetime import date, datetime
from typing import Literal

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
InsightStatus = Literal["candidate", "active", "rejected", "archived"]
MessageRole = Literal["user", "assistant", "system"]
SearchObjectType = Literal["source_document", "journal_entry", "daily_checkin", "task", "goal"]


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




PromptId = Literal["open_tasks", "recent_checkins", "recent_journal", "active_goals"]


class GuidedPrompt(BaseModel):
    id: PromptId
    label: str
    description: str
    results: list[SearchResult] = Field(default_factory=list)


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


