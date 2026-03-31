from __future__ import annotations

from datetime import datetime, timezone
import re

from ..schemas import (
    ChatRequest,
    ChatResponse,
    DailyCheckinCreate,
    ExtractionSummary,
    GoalCreate,
    JournalEntryCreate,
    SourceDocumentCreate,
    TaskCreate,
)
from ..storage.repository import Repository
from .llm import generate_chat_reply


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


def _build_memory_context(repo: Repository, user_id: str, conversation_id: str) -> list[str]:
    context: list[str] = []

    open_tasks = repo.list_open_tasks(user_id=user_id, limit=3)
    if open_tasks:
        task_text = "; ".join(task.title for task in open_tasks)
        context.append(f"Open tasks: {task_text}")

    recent_messages = repo.list_conversation_messages(conversation_id=conversation_id, limit=6, user_id=user_id)
    user_messages = [m.content for m in recent_messages if m.role == "user"]
    if user_messages:
        context.append(f"Recent user focus: {user_messages[-1][:160]}")

    recent_checkins = repo.list_checkins(user_id)
    if recent_checkins:
        latest = recent_checkins[0]
        parts: list[str] = []
        if latest.sleep_hours is not None:
            parts.append(f"sleep {latest.sleep_hours}h")
        if latest.mood is not None:
            parts.append(f"mood {latest.mood}/10")
        if latest.energy is not None:
            parts.append(f"energy {latest.energy}/10")
        if parts:
            context.append(f"Latest check-in ({latest.date.isoformat()}): " + ", ".join(parts))

    return context


def handle_chat(repo: Repository, payload: ChatRequest) -> ChatResponse:
    now = datetime.now(timezone.utc)
    conversation = repo.get_or_create_conversation(
        user_id=payload.user_id,
        conversation_id=payload.conversation_id,
        title="MemoryChain Chat",
    )

    source = repo.create_source_document(
        SourceDocumentCreate(
            user_id=payload.user_id,
            source_type="chat_message",
            effective_at=now,
            title="Chat message",
            raw_text=payload.message,
            metadata={"conversation_id": conversation.id},
        )
    )

    journal = repo.create_journal_entry(
        JournalEntryCreate(
            user_id=payload.user_id,
            source_document_id=source.id,
            effective_at=now,
            entry_type="journal",
            title="Chat capture",
            text=payload.message,
            tags=["chat"],
        )
    )

    checkin_payload = _extract_checkin(
        user_id=payload.user_id,
        source_document_id=source.id,
        text=payload.message,
        effective_at=now,
    )
    checkin = repo.create_checkin(checkin_payload) if checkin_payload else None

    goals = [repo.create_goal(goal) for goal in _extract_goals(payload.user_id, payload.message)]
    tasks = [repo.create_task(task) for task in _extract_tasks(payload.user_id, payload.message)]

    repo.append_conversation_message(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        role="user",
        content=payload.message,
        source_document_id=source.id,
    )

    history = repo.list_conversation_messages(conversation_id=conversation.id, limit=10, user_id=payload.user_id)
    history_lines = [f"{msg.role}: {msg.content}" for msg in history]
    memory_context = _build_memory_context(repo, payload.user_id, conversation.id)

    assistant_text = generate_chat_reply(
        user_message=payload.message,
        memory_context=memory_context,
        history_lines=history_lines,
    )

    assistant_msg = repo.append_conversation_message(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        role="assistant",
        content=assistant_text,
    )

    return ChatResponse(
        conversation_id=conversation.id,
        assistant_message=assistant_text,
        assistant_message_id=assistant_msg.id,
        extraction=ExtractionSummary(
            source_document_id=source.id,
            journal_entry_id=journal.id,
            checkin_id=checkin.id if checkin else None,
            task_ids=[task.id for task in tasks],
            goal_ids=[goal.id for goal in goals],
        ),
        memory_context=memory_context,
    )