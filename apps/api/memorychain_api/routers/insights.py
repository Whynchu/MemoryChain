from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Insight, InsightCreate, InsightUpdate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])


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
