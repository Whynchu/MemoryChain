from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Task, TaskCreate, TaskUpdate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=Task)
def create_task(payload: TaskCreate, repo: Repository = Depends(protected_repo)) -> Task:
    return repo.create_task(payload)


@router.get("", response_model=list[Task])
def list_tasks(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Task]:
    return repo.list_tasks(user_id=user_id, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Task:
    task = repo.get_task(task_id=task_id, user_id=user_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=Task)
def update_task(task_id: str, user_id: str, payload: TaskUpdate, repo: Repository = Depends(protected_repo)) -> Task:
    updated = repo.update_task(task_id=task_id, user_id=user_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return updated
