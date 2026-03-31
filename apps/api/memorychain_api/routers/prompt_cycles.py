from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import (
    PromptCycle,
    PromptCycleEventRequest,
    PromptCycleRespondRequest,
    PromptCycleScheduleRequest,
)
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/prompt-cycles", tags=["prompt-cycles"])


def _event_time(value: datetime | None) -> datetime:
    return value or datetime.now(timezone.utc)


@router.post("/schedule", response_model=PromptCycle)
def schedule_prompt_cycle(
    payload: PromptCycleScheduleRequest,
    repo: Repository = Depends(protected_repo),
) -> PromptCycle:
    return repo.create_prompt_cycle(
        user_id=payload.user_id,
        cycle_date=payload.cycle_date,
        scheduled_for=payload.scheduled_for,
        expires_at=payload.expires_at,
    )


@router.post("/{cycle_id}/send", response_model=PromptCycle)
def send_prompt_cycle(
    cycle_id: str,
    payload: PromptCycleEventRequest,
    repo: Repository = Depends(protected_repo),
) -> PromptCycle:
    try:
        updated = repo.send_prompt_cycle(
            cycle_id=cycle_id,
            user_id=payload.user_id,
            event_at=_event_time(payload.event_at),
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt cycle not found")
    return updated


@router.post("/{cycle_id}/viewed", response_model=PromptCycle)
def view_prompt_cycle(
    cycle_id: str,
    payload: PromptCycleEventRequest,
    repo: Repository = Depends(protected_repo),
) -> PromptCycle:
    try:
        updated = repo.mark_prompt_cycle_viewed(
            cycle_id=cycle_id,
            user_id=payload.user_id,
            event_at=_event_time(payload.event_at),
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt cycle not found")
    return updated


@router.post("/{cycle_id}/responded", response_model=PromptCycle)
def respond_prompt_cycle(
    cycle_id: str,
    payload: PromptCycleRespondRequest,
    repo: Repository = Depends(protected_repo),
) -> PromptCycle:
    try:
        updated = repo.mark_prompt_cycle_responded(
            cycle_id=cycle_id,
            user_id=payload.user_id,
            event_at=_event_time(payload.event_at),
            response_source_document_id=payload.response_source_document_id,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt cycle not found")
    return updated


@router.post("/{cycle_id}/missed", response_model=PromptCycle)
def miss_prompt_cycle(
    cycle_id: str,
    payload: PromptCycleEventRequest,
    repo: Repository = Depends(protected_repo),
) -> PromptCycle:
    try:
        updated = repo.mark_prompt_cycle_missed(
            cycle_id=cycle_id,
            user_id=payload.user_id,
            event_at=_event_time(payload.event_at),
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt cycle not found")
    return updated


@router.get("", response_model=list[PromptCycle])
def list_prompt_cycles(
    user_id: str,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    repo: Repository = Depends(protected_repo),
) -> list[PromptCycle]:
    return repo.list_prompt_cycles(user_id=user_id, date_from=from_date, date_to=to_date)
