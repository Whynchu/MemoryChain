from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import GuidedPromptsResponse
from ..services.guided_prompts import get_guided_prompts
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["prompts"])


@router.get("/prompts", response_model=GuidedPromptsResponse)
def list_guided_prompts(user_id: str, repo: Repository = Depends(protected_repo)) -> GuidedPromptsResponse:
    return get_guided_prompts(repo, user_id=user_id)
