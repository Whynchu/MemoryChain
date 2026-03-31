from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import Task, TaskCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=Task)
def create_task(payload: TaskCreate, repo: Repository = Depends(protected_repo)) -> Task:
    return repo.create_task(payload)


@router.get("", response_model=list[Task])
def list_tasks(user_id: str, repo: Repository = Depends(protected_repo)) -> list[Task]:
    return repo.list_tasks(user_id)
