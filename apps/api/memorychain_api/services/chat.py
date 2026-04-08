from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import (
    CompanionAction,
    CompanionDirective,
    ChatRequest,
    ChatResponse,
    ExtractionSummary,
    SourceDocumentCreate,
)
from ..storage.repository import Repository
from .companion_actions import build_companion_actions
from .companion_execution import CompanionExecutionResult, execute_pending_companion
from .companion_orchestrator import orchestrate_companion
from .companion_state import (
    advance_pending_companion,
    apply_pending_action_intent,
    load_pending_companion,
    persist_pending_companion,
    should_consume_pending_companion,
)
from .context_snapshot import build_context_snapshot
from .extraction import extract_objects
from .intent import ClassificationResult, classify_intent
from .llm import generate_companion_reply, generate_log_reply, generate_query_reply
from .query_handler import handle_query
from .questionnaire import QuestionnaireService, is_questionnaire_command


def _questionnaire_companion() -> CompanionDirective:
    return CompanionDirective(
        mode="intake",
        active_thread="questionnaire",
        rationale=["Questionnaire flow is active, so structured intake takes precedence."],
        signals=[],
        actions=[
            CompanionAction(
                kind="clarify",
                prompt="Answer the current questionnaire prompt directly so I can keep the intake clean.",
                reason="A questionnaire session is already in progress.",
                expected_response="questionnaire_answer",
            )
        ],
    )


def _build_companion(
    *,
    user_message: str,
    classification: ClassificationResult,
    snapshot,
) -> CompanionDirective:
    companion = orchestrate_companion(
        user_message=user_message,
        classification=classification,
        snapshot=snapshot,
    )
    companion.actions = build_companion_actions(
        user_message=user_message,
        snapshot=snapshot,
        directive=companion,
    )
    return companion


def _continue_companion(snapshot) -> CompanionDirective:
    return _build_companion(
        user_message="continue",
        classification=ClassificationResult(
            intent="chat",
            confidence=1.0,
            reasoning="advance companion thread",
        ),
        snapshot=snapshot,
    )


def _resolve_companion_after_pending(
    *,
    pending_companion: CompanionDirective,
    snapshot,
    execution: CompanionExecutionResult | None,
) -> CompanionDirective:
    if execution is None:
        return advance_pending_companion(
            pending=pending_companion,
            snapshot=snapshot,
        ) or _continue_companion(snapshot)
    if execution is not None and execution.keep_pending:
        return pending_companion
    if execution is not None and execution.should_advance:
        return advance_pending_companion(
            pending=pending_companion,
            snapshot=snapshot,
        ) or _continue_companion(snapshot)
    return _continue_companion(snapshot)


def handle_chat(repo: Repository, payload: ChatRequest) -> ChatResponse:
    now = datetime.now(timezone.utc)
    conversation = repo.get_or_create_conversation(
        user_id=payload.user_id,
        conversation_id=payload.conversation_id,
        title="MemoryChain Chat",
    )
    pending_companion = load_pending_companion(conversation)

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
        questionnaire_companion = _questionnaire_companion()
        persist_pending_companion(
            repo=repo,
            conversation=conversation,
            user_id=payload.user_id,
            companion=questionnaire_companion,
        )
        
        return ChatResponse(
            conversation_id=conversation.id,
            assistant_message=assistant_text,
            assistant_message_id=assistant_msg.id,
            extraction=ExtractionSummary(source_document_id=source.id),
            memory_context=[],
            companion=questionnaire_companion,
        )
    
    # Check if this is a questionnaire command
    template_name = is_questionnaire_command(payload.message)
    if template_name:
        # Find template by name (check user templates first, then system)
        templates = repo.list_questionnaire_templates(payload.user_id, active_only=True)
        template = next((t for t in templates if t.name.lower() == template_name), None)
        if not template:
            system_templates = repo.list_questionnaire_templates("system", active_only=True)
            template = next((t for t in system_templates if t.name.lower() == template_name), None)
        
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
            questionnaire_companion = _questionnaire_companion()
            persist_pending_companion(
                repo=repo,
                conversation=conversation,
                user_id=payload.user_id,
                companion=questionnaire_companion,
            )
            
            return ChatResponse(
                conversation_id=conversation.id,
                assistant_message=assistant_text,
                assistant_message_id=assistant_msg.id,
                extraction=ExtractionSummary(source_document_id=source.id),
                memory_context=[],
                companion=questionnaire_companion,
            )
        else:
            # Template not found - fall through to normal chat
            pass

    # ── Phase 5: Intent-aware routing ──────────────────────
    classification = classify_intent(payload.message)
    classification = apply_pending_action_intent(
        classification=classification,
        pending=pending_companion,
    )
    consume_pending = should_consume_pending_companion(
        user_message=payload.message,
        classification=classification,
        pending=pending_companion,
    )

    # Close active log session on non-log intent
    if classification.intent != "log":
        repo.close_log_session(conversation.id)

    # Store user message in conversation history (always, for all intents)
    repo.append_conversation_message(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        role="user",
        content=payload.message,
    )

    history = repo.list_conversation_messages(conversation_id=conversation.id, limit=10, user_id=payload.user_id)
    history_lines = [f"{msg.role}: {msg.content}" for msg in history]
    snapshot = build_context_snapshot(repo, payload.user_id)
    memory_context = snapshot.to_memory_context()
    pending_execution: CompanionExecutionResult | None = None
    if consume_pending and classification.intent == "chat" and pending_companion is not None:
        pending_execution = execute_pending_companion(
            repo=repo,
            user_id=payload.user_id,
            pending=pending_companion,
            user_message=payload.message,
        )
        if pending_execution.applied:
            snapshot = build_context_snapshot(repo, payload.user_id)
            memory_context = snapshot.to_memory_context()
    if consume_pending and classification.intent == "chat" and pending_companion is not None:
        companion = _resolve_companion_after_pending(
            pending_companion=pending_companion,
            snapshot=snapshot,
            execution=pending_execution,
        )
    else:
        companion = _build_companion(
            user_message=payload.message,
            classification=classification,
            snapshot=snapshot,
        )

    if classification.intent == "log":
        return _handle_log(
            repo,
            payload,
            conversation,
            now,
            memory_context,
            history_lines,
            companion,
            pending_companion,
            consume_pending,
        )
    elif classification.intent == "query":
        return _handle_query(repo, payload, conversation, memory_context, history_lines, companion)
    else:
        return _handle_chat(
            repo,
            payload,
            conversation,
            snapshot,
            memory_context,
            history_lines,
            companion,
            execution_note=pending_execution.assistant_note if pending_execution else None,
            note_only=bool(pending_execution and pending_execution.keep_pending),
        )


def _handle_log(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    now,
    memory_context: list[str],
    history_lines: list[str],
    companion: CompanionDirective,
    pending_companion: CompanionDirective | None,
    consume_pending: bool,
) -> ChatResponse:
    """LOG intent: extract data, store everything, confirm what was stored."""

    # Check for active log session in this conversation
    active_source = repo.find_active_log_source(conversation_id=conversation.id)

    if active_source:
        msg_count = active_source.metadata.get("log_message_count", 1)
        if msg_count >= 10:
            active_source = None  # Force new session

    if active_source:
        # ── APPEND mode: extend existing log session ──
        source = repo.update_source_document_text(
            active_source.id, payload.message, now
        )
        new_count = active_source.metadata.get("log_message_count", 1) + 1
        repo.update_source_document_metadata(source.id, {
            **active_source.metadata,
            "log_message_count": new_count,
        })
    else:
        # ── CREATE mode: start new log session ──
        source = repo.create_source_document(
            SourceDocumentCreate(
                user_id=payload.user_id,
                source_type="chat_message",
                effective_at=now,
                title="Chat message",
                raw_text=payload.message,
                metadata={
                    "conversation_id": conversation.id,
                    "log_session_active": True,
                    "log_message_count": 1,
                },
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

    # Handle journal entry — append if one exists for this source, else create
    journal = None
    if extraction.journal_entry:
        existing_journal = repo.find_journal_by_source(source.id)
        if existing_journal:
            repo.update_journal_entry_text(existing_journal.id, extraction.journal_entry.text)
            journal = existing_journal
        else:
            journal = repo.create_journal_entry(extraction.journal_entry)

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
    refreshed_snapshot = build_context_snapshot(repo, payload.user_id)
    response_companion = companion
    if consume_pending and pending_companion is not None:
        response_companion = _resolve_companion_after_pending(
            pending_companion=pending_companion,
            snapshot=refreshed_snapshot,
            execution=None,
        )
    persist_pending_companion(
        repo=repo,
        conversation=conversation,
        user_id=payload.user_id,
        companion=response_companion,
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
        memory_context=refreshed_snapshot.to_memory_context(),
        companion=response_companion,
    )


def _handle_query(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    memory_context: list[str],
    history_lines: list[str],
    companion: CompanionDirective,
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
    persist_pending_companion(
        repo=repo,
        conversation=conversation,
        user_id=payload.user_id,
        companion=companion,
    )

    return ChatResponse(
        conversation_id=conversation.id,
        assistant_message=assistant_text,
        assistant_message_id=assistant_msg.id,
        extraction=ExtractionSummary(),
        memory_context=memory_context,
        companion=companion,
    )


def _handle_chat(
    repo: Repository,
    payload: ChatRequest,
    conversation,
    snapshot,
    memory_context: list[str],
    history_lines: list[str],
    companion: CompanionDirective,
    execution_note: str | None = None,
    note_only: bool = False,
) -> ChatResponse:
    """CHAT intent: conversational reply. No extraction, no storage."""
    if note_only and execution_note:
        assistant_text = execution_note
    else:
        assistant_text = generate_companion_reply(
            user_message=payload.message,
            snapshot=snapshot,
            directive=companion,
            history_lines=history_lines,
            execution_note=execution_note,
        )

    assistant_msg = repo.append_conversation_message(
        conversation_id=conversation.id,
        user_id=payload.user_id,
        role="assistant",
        content=assistant_text,
    )
    persist_pending_companion(
        repo=repo,
        conversation=conversation,
        user_id=payload.user_id,
        companion=companion,
    )

    return ChatResponse(
        conversation_id=conversation.id,
        assistant_message=assistant_text,
        assistant_message_id=assistant_msg.id,
        extraction=ExtractionSummary(),
        memory_context=memory_context,
        companion=companion,
    )
