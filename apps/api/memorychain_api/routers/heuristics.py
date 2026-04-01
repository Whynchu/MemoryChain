from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Heuristic, HeuristicCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/heuristics", tags=["heuristics"])


@router.post("", response_model=Heuristic)
def create_heuristic(payload: HeuristicCreate, repo: Repository = Depends(protected_repo)) -> Heuristic:
    return repo.create_heuristic(payload)


@router.get("", response_model=list[Heuristic])
def list_heuristics(
    user_id: str,
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Heuristic]:
    return repo.list_heuristics(user_id=user_id, active_only=active_only, limit=limit, offset=offset)


@router.get("/{heuristic_id}", response_model=Heuristic)
def get_heuristic(heuristic_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Heuristic:
    heuristic = repo.get_heuristic(heuristic_id=heuristic_id, user_id=user_id)
    if heuristic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Heuristic not found")
    return heuristic
