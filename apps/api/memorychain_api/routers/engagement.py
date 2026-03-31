from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import EngagementSummary
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/engagement", tags=["engagement"])


@router.get("/summary", response_model=EngagementSummary)
def get_engagement_summary(
    user_id: str,
    window: str = Query(default="7d", pattern="^(7d|30d)$"),
    repo: Repository = Depends(protected_repo),
) -> EngagementSummary:
    window_days = 7 if window == "7d" else 30
    try:
        return repo.get_engagement_summary(user_id=user_id, window_days=window_days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
