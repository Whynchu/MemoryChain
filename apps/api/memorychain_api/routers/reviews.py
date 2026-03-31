from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import WeeklyReview, WeeklyReviewRequest
from ..services.weekly_review import generate_weekly_review
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/weekly-reviews", tags=["weekly-reviews"])


@router.post("/generate", response_model=WeeklyReview)
def generate(payload: WeeklyReviewRequest, repo: Repository = Depends(protected_repo)) -> WeeklyReview:
    return generate_weekly_review(
        repo,
        user_id=payload.user_id,
        week_start=payload.week_start,
        week_end=payload.week_end,
    )


@router.get("", response_model=list[WeeklyReview])
def list_weekly_reviews(user_id: str, repo: Repository = Depends(protected_repo)) -> list[WeeklyReview]:
    return repo.list_weekly_reviews(user_id)
