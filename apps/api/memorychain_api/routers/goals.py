from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Goal, GoalCreate, GoalUpdate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


@router.post("", response_model=Goal)
def create_goal(payload: GoalCreate, repo: Repository = Depends(protected_repo)) -> Goal:
    return repo.create_goal(payload)


@router.get("", response_model=list[Goal])
def list_goals(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Goal]:
    return repo.list_goals(user_id=user_id, limit=limit, offset=offset)


@router.get("/{goal_id}", response_model=Goal)
def get_goal(goal_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Goal:
    goal = repo.get_goal(goal_id=goal_id, user_id=user_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.put("/{goal_id}", response_model=Goal)
def update_goal(goal_id: str, user_id: str, payload: GoalUpdate, repo: Repository = Depends(protected_repo)) -> Goal:
    updated = repo.update_goal(goal_id=goal_id, user_id=user_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return updated
