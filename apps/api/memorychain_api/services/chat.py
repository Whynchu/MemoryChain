from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import (
    ChatRequest,
    ChatResponse,
    ExtractionSummary,
    SourceDocumentCreate,
)
from ..storage.repository import Repository
from .extraction import extract_objects, is_substantive
from .intent import classify_intent
from .llm import generate_chat_reply, generate_log_reply, generate_query_reply
from .query_handler import handle_query
from .questionnaire import QuestionnaireService, is_questionnaire_command


def _build_memory_context(repo: Repository, user_id: str, conversation_id: str) -> list[str]:
    context: list[str] = []
    now = datetime.now()

    # Time awareness — local time, day of week, time-of-day period
    day_name = now.strftime("%A")
    time_str = now.strftime("%I:%M %p").lstrip("0")
    hour = now.hour
    if hour < 6:
        period = "late night"
    elif hour < 9:
        period = "early morning"
    elif hour < 12:
        period = "morning"
    elif hour < 14:
        period = "early afternoon"
    elif hour < 17:
        period = "afternoon"
    elif hour < 20:
        period = "evening"
    else:
        period = "night"
    context.append(f"Current time: {day_name} {time_str} ({period})")

    # Open tasks — what's on the user's plate
    open_tasks = repo.list_open_tasks(user_id=user_id, limit=5)
    if open_tasks:
        task_text = "; ".join(task.title for task in open_tasks[:3])
        context.append(f"Open tasks ({len(open_tasks)}): {task_text}")

    # Active goals — what they're working toward
    active_goals = repo.list_goals(user_id=user_id, limit=5)
    active_goals = [g for g in active_goals if g.status == "active"]
    if active_goals:
        goal_text = "; ".join(g.title for g in active_goals[:3])
        context.append(f"Active goals ({len(active_goals)}): {goal_text}")

    # Recent check-in — how they've been feeling
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

        # Flag if no check-in today
        today = now.date()
        if latest.date and latest.date < today:
            days_since = (today - latest.date).days
            context.append(f"No check-in today (last was {days_since} day(s) ago)")
    else:
        context.append("No check-ins recorded yet — user is new")

    return context


def handle_chat(repo: Repository, payload: ChatRequest) -> ChatResponse:
    now = datetime.now(timezone.utc)
    conversation = repo.get_or_create_conversation(
        user_id=payload.user_id,
        conversation_id=payload.conversation_id,
        title="MemoryChain Chat",
    )

    # Check for active questionnaire session first
    q_service = QuestionnaireService(repo)
    active_session = q_service.check_active_session(payload.user_id, conversation.id)
    
    if active_session:
        # User is in middle of questionnaire - process their answer
        next_question, is_complete = q_service.process_answer(active_session, payload.message)
        
        # Store user message
        source = repo.create_source_document(
            SourceDocumentCreate(
                user_id=payload.user_id,
                source_type="chat_message",
                effective_at=now,
                title="Questionnaire response",
                raw_text=payload.message,
                metadata={"conversation_id": conversation.id, "questionnaire_session_id": active_session.id},
            )
        )
        
        repo.append_conversation_message(
            conversation_id=conversation.id,
            user_id=payload.user_id,
            role="user",
            content=payload.message,
            source_document_id=source.id,
        )
        
        # Send questionnaire response
        assistant_text = next_question if next_question else "All done! What else can I help you with?"
        
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
            extraction=ExtractionSummary(source_document_id=source.id),
            memory_context=[],
        )
    
    # Check if this is a questionnaire command
    template_name = is_questionnaire_command(payload.message)
    if template_name:
        # Find template by name
        templates = repo.list_questionnaire_templates(payload.user_id, active_only=True)
        template = next((t for t in templates if t.name.lower() == template_name), None)
        
        if template:
            # Start questionnaire
            session, first_question = q_service.start_questionnaire(
                payload.user_id, template.id, conversation.id
            )
            
            # Store user command
            source = repo.create_source_document(
                SourceDocumentCreate(
                    user_id=payload.user_id,
                    source_type="chat_message",
                    effective_at=now,
                    title="Questionnaire start command",
                    raw_text=payload.message,
                    metadata={"conversation_id": conversation.id},
                )
            )
            
            repo.append_conversation_message(
                conversation_id=conversation.id,
                user_id=payload.user_id,
                role="user",
                content=payload.message,
                source_document_id=source.id,
            )
            
            # Ask first question
            assistant_text = f"Starting **{template.name}**\n\n{first_question}"
            
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
                extraction=ExtractionSummary(source_document_id=source.id),
                memory_context=[],
            )
        else:
            # Template not found - fall through to normal chat
            pass

    # ── Phase 5: Intent-aware routing ──────────────────────
    classification = classify_intent(payload.message)

    # Store user message in conversation history (always, for all intents)
    repo.append_conversation_message(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        role="user",
        content=payload.message,
    )

    history = repo.list_conversation_messages(conversation_id=conversation.id, limit=10, user_id=payload.user_id)
    history_lines = [f"{msg.role}: {msg.content}" for msg in history]
    memory_context = _build_memory_context(repo, payload.user_id, conversation.id)

    if classification.intent == "log":
        return _handle_log(repo, payload, conversation, now, memory_context, history_lines)
    elif classification.intent == "query":
        return _handle_query(repo, payload, conversation, memory_context, history_lines)
    else:
        return _handle_chat(repo, payload, conversation, memory_context, history_lines)


def _handle_log(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    now,
    memory_context: list[str],
    history_lines: list[str],
) -> ChatResponse:
    """LOG intent: extract data, store everything, confirm what was stored."""
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

    extraction = extract_objects(
        raw_text=payload.message,
        source_document_id=source.id,
        user_id=payload.user_id,
        effective_at=now,
        create_journal=True,
        provenance="user",
        provider="hybrid",
    )

    journal = repo.create_journal_entry(extraction.journal_entry) if extraction.journal_entry else None
    checkin = repo.create_checkin(extraction.checkin) if extraction.checkin else None
    goals = [repo.create_goal(g) for g in extraction.goals]
    tasks = [repo.create_task(t) for t in extraction.tasks]
    activities = [repo.create_activity(a) for a in extraction.activities]
    metrics = [repo.create_metric_observation(m) for m in extraction.metrics]

    # Build extraction summary for reply generation
    extraction_summary = []
    if checkin:
        parts = []
        if checkin.sleep_hours is not None:
            parts.append(f"sleep {checkin.sleep_hours}h")
        if checkin.mood is not None:
            parts.append(f"mood {checkin.mood}/10")
        if checkin.energy is not None:
            parts.append(f"energy {checkin.energy}/10")
        if parts:
            extraction_summary.append(f"Check-in: {', '.join(parts)}")
    if journal:
        extraction_summary.append(f"Journal entry recorded")
    for g in goals:
        extraction_summary.append(f"Goal: {g.title}")
    for t in tasks:
        extraction_summary.append(f"Task: {t.title}")
    for a in activities:
        extraction_summary.append(f"Activity: {a.title}")

    assistant_text = generate_log_reply(
        user_message=payload.message,
        memory_context=memory_context,
        extraction_summary=extraction_summary,
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
            journal_entry_id=journal.id if journal else None,
            checkin_id=checkin.id if checkin else None,
            task_ids=[task.id for task in tasks],
            goal_ids=[goal.id for goal in goals],
            activity_ids=[a.id for a in activities],
            metric_ids=[m.id for m in metrics],
        ),
        memory_context=memory_context,
    )


def _handle_query(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    memory_context: list[str],
    history_lines: list[str],
) -> ChatResponse:
    """QUERY intent: retrieve data, respond with real numbers. No storage."""
    results = handle_query(repo, payload.user_id, payload.message)

    query_context = []
    for r in results:
        query_context.append(r.summary)
        query_context.extend(r.data_lines)

    assistant_text = generate_query_reply(
        user_message=payload.message,
        query_context=query_context,
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
        extraction=ExtractionSummary(),
        memory_context=memory_context,
    )


def _handle_chat(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    memory_context: list[str],
    history_lines: list[str],
) -> ChatResponse:
    """CHAT intent: conversational reply. No extraction, no storage."""
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
        extraction=ExtractionSummary(),
        memory_context=memory_context,
    )