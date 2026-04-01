from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Activity, ActivityCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


@router.post("", response_model=Activity)
def create_activity(payload: ActivityCreate, repo: Repository = Depends(protected_repo)) -> Activity:
    return repo.create_activity(payload)


@router.get("", response_model=list[Activity])
def list_activities(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Activity]:
    return repo.list_activities(user_id=user_id, limit=limit, offset=offset)


@router.get("/{activity_id}", response_model=Activity)
def get_activity(activity_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Activity:
    activity = repo.get_activity(activity_id=activity_id, user_id=user_id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity
