from __future__ import annotations

from ..schemas import (
    DailyCheckinCreate,
    IngestRequest,
    IngestResponse,
    JournalEntryCreate,
)
from ..storage.repository import Repository
from .extraction import extract_objects


def ingest(repo: Repository, payload: IngestRequest) -> IngestResponse:
    duplicate_source = repo.find_duplicate_source(
        raw_text=payload.source.raw_text,
        effective_at=payload.source.effective_at,
    )
    if duplicate_source:
        return IngestResponse(source_document=duplicate_source, duplicate=True)

    source = repo.create_source_document(payload.source)

    journal_create: JournalEntryCreate | None = None
    checkin_create: DailyCheckinCreate | None = None

    if payload.journal_entry is None and payload.checkin is None:
        # No explicit structured data — run extraction on the raw text
        extraction = extract_objects(
            raw_text=payload.source.raw_text,
            source_document_id=source.id,
            user_id=payload.source.user_id,
            effective_at=payload.source.effective_at,
            create_journal=True,
            provenance=payload.source.source_type,
        )
        journal_create = extraction.journal_entry
        checkin_create = extraction.checkin
        # Also persist extracted activities and metrics
        for act in extraction.activities:
            repo.create_activity(act)
        for met in extraction.metrics:
            repo.create_metric_observation(met)
        for goal in extraction.goals:
            repo.create_goal(goal)
        for task in extraction.tasks:
            repo.create_task(task)
    else:
        if payload.journal_entry is not None:
            journal_create = JournalEntryCreate(
                user_id=payload.source.user_id,
                source_document_id=source.id,
                effective_at=payload.journal_entry.effective_at or payload.source.effective_at,
                entry_type=payload.journal_entry.entry_type,
                title=payload.journal_entry.title,
                text=payload.journal_entry.text,
                tags=payload.journal_entry.tags,
            )
        if payload.checkin is not None:
            checkin_create = DailyCheckinCreate(
                user_id=payload.source.user_id,
                source_document_id=source.id,
                date=payload.checkin.date,
                effective_at=payload.checkin.effective_at or payload.source.effective_at,
                sleep_hours=payload.checkin.sleep_hours,
                sleep_quality=payload.checkin.sleep_quality,
                mood=payload.checkin.mood,
                energy=payload.checkin.energy,
                body_weight=payload.checkin.body_weight,
                body_weight_unit=payload.checkin.body_weight_unit,
                immediate_thoughts=payload.checkin.immediate_thoughts,
                pain_notes=payload.checkin.pain_notes,
                hydration_start=payload.checkin.hydration_start,
                hydration_unit=payload.checkin.hydration_unit,
            )

    created_journal = repo.create_journal_entry(journal_create) if journal_create else None
    created_checkin = repo.create_checkin(checkin_create) if checkin_create else None
    return IngestResponse(
        source_document=source,
        journal_entry=created_journal,
        checkin=created_checkin,
        duplicate=False,
    )
