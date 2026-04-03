from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..dependencies import protected_repo
from ..schemas import Heuristic, HeuristicCreate, Insight, InsightCreate, InsightUpdate
from ..services.insight_detection import run_all_detectors
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


# -- Request / response models for new endpoints --


class DetectRequest(BaseModel):
    user_id: str


class StatusChangeRequest(BaseModel):
    status: str
    reason: str | None = None


# Valid status transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"active", "rejected", "archived"},
    "active": {"promoted", "rejected", "archived"},
    "rejected": {"archived"},
    "archived": set(),
    "promoted": set(),
}

# Promotion thresholds
MIN_EVIDENCE_COUNT = 5
MIN_SPAN_WEEKS = 3


@router.post("", response_model=Insight)
def create_insight(payload: InsightCreate, repo: Repository = Depends(protected_repo)) -> Insight:
    return repo.create_insight(payload)


@router.get("", response_model=list[Insight])
def list_insights(
    user_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Insight]:
    return repo.list_insights(user_id=user_id, status=status_filter, limit=limit, offset=offset)


@router.get("/{insight_id}", response_model=Insight)
def get_insight(insight_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Insight:
    insight = repo.get_insight(insight_id=insight_id, user_id=user_id)
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    return insight


@router.put("/{insight_id}", response_model=Insight)
def update_insight(
    insight_id: str, user_id: str, payload: InsightUpdate,
    repo: Repository = Depends(protected_repo),
) -> Insight:
    updated = repo.update_insight(insight_id=insight_id, user_id=user_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    return updated


# -- Phase 2 endpoints --


@router.post("/detect", response_model=list[Insight])
def detect_insights(payload: DetectRequest, repo: Repository = Depends(protected_repo)) -> list[Insight]:
    """Run all registered insight detectors for a user.

    Idempotent — re-running won't duplicate insights (detector_key dedup).
    Rejected detector_keys are never re-created.
    """
    return run_all_detectors(repo, payload.user_id)


@router.put("/{insight_id}/status", response_model=Insight)
def change_insight_status(
    insight_id: str,
    user_id: str,
    payload: StatusChangeRequest,
    repo: Repository = Depends(protected_repo),
) -> Insight:
    """Change insight status with state machine enforcement.

    Valid transitions:
      candidate → active | rejected | archived
      active    → promoted (via /promote only) | rejected | archived
      rejected  → archived
    """
    insight = repo.get_insight(insight_id=insight_id, user_id=user_id)
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    new_status = payload.status
    if new_status == "promoted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /api/v1/insights/{id}/promote to promote insights",
        )

    valid_next = _VALID_TRANSITIONS.get(insight.status, set())
    if new_status not in valid_next:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from '{insight.status}' to '{new_status}'. "
                   f"Valid transitions: {sorted(valid_next) or 'none (terminal state)'}",
        )

    update = InsightUpdate(status=new_status)
    updated = repo.update_insight(insight_id=insight_id, user_id=user_id, payload=update)
    return updated


@router.post("/{insight_id}/promote", response_model=Heuristic)
def promote_insight(
    insight_id: str,
    user_id: str,
    repo: Repository = Depends(protected_repo),
) -> Heuristic:
    """Promote an active insight to a heuristic rule.

    Validates:
      - Insight status must be 'active'
      - ≥ 5 evidence items
      - Pattern spans ≥ 3 weeks
      - Counter-evidence ratio ≤ 1:3
    """
    insight = repo.get_insight(insight_id=insight_id, user_id=user_id)
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    # Run all threshold checks, report all failures at once
    checks: dict[str, bool | str] = {}
    failures: list[str] = []

    # Status check
    if insight.status != "active":
        checks["status_is_active"] = f"actual: {insight.status}"
        failures.append(f"Insight status must be 'active', got '{insight.status}'")
    else:
        checks["status_is_active"] = True

    # Evidence count
    evidence_count = len(insight.evidence_ids)
    if evidence_count < MIN_EVIDENCE_COUNT:
        checks["min_evidence"] = f"{evidence_count}/{MIN_EVIDENCE_COUNT}"
        failures.append(f"Need ≥{MIN_EVIDENCE_COUNT} evidence items, got {evidence_count}")
    else:
        checks["min_evidence"] = True

    # Time span
    span_days = 0
    if insight.time_window_start and insight.time_window_end:
        span_days = (insight.time_window_end - insight.time_window_start).days
    min_span_days = MIN_SPAN_WEEKS * 7
    if span_days < min_span_days:
        checks["min_span"] = f"{span_days}/{min_span_days} days"
        failures.append(f"Pattern must span ≥{MIN_SPAN_WEEKS} weeks ({min_span_days} days), got {span_days} days")
    else:
        checks["min_span"] = True

    # Counter-evidence ratio
    counter_count = len(insight.counterevidence_ids)
    if evidence_count > 0 and counter_count > evidence_count / 3:
        checks["counter_ratio"] = f"{counter_count}:{evidence_count} (max 1:3)"
        failures.append(
            f"Counter-evidence ratio too high: {counter_count} counter vs {evidence_count} supporting (max 1:3)"
        )
    else:
        checks["counter_ratio"] = True

    if failures:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Promotion thresholds not met",
                "failures": failures,
                "checks": checks,
            },
        )

    # Create the heuristic
    snapshot = {
        "thresholds": {
            "min_evidence": MIN_EVIDENCE_COUNT,
            "min_span_weeks": MIN_SPAN_WEEKS,
            "max_counter_ratio": "1:3",
        },
        "values_at_promotion": {
            "evidence_count": evidence_count,
            "counter_evidence_count": counter_count,
            "span_days": span_days,
            "confidence": insight.confidence,
        },
    }

    heuristic = repo.create_heuristic(
        HeuristicCreate(
            user_id=user_id,
            rule=f"[auto] {insight.title}: {insight.summary}",
            source_type="validated_pattern",
            confidence=insight.confidence,
            evidence_ids=insight.evidence_ids,
            counterevidence_ids=insight.counterevidence_ids,
            validation_notes=f"Promoted from insight {insight_id}",
            insight_id=insight_id,
            promotion_snapshot=snapshot,
        )
    )

    # Update insight status to promoted
    repo.update_insight(
        insight_id=insight_id,
        user_id=user_id,
        payload=InsightUpdate(status="promoted"),
    )

    return heuristic
