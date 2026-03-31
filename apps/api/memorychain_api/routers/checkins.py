from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import DailyCheckin
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/checkins", tags=["checkins"])


@router.get("", response_model=list[DailyCheckin])
def list_checkins(user_id: str, repo: Repository = Depends(protected_repo)) -> list[DailyCheckin]:
    return repo.list_checkins(user_id)
