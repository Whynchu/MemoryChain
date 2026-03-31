from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import Goal, GoalCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


@router.post("", response_model=Goal)
def create_goal(payload: GoalCreate, repo: Repository = Depends(protected_repo)) -> Goal:
    return repo.create_goal(payload)


@router.get("", response_model=list[Goal])
def list_goals(user_id: str, repo: Repository = Depends(protected_repo)) -> list[Goal]:
    return repo.list_goals(user_id)
