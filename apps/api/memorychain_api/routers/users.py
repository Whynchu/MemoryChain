"""User profile endpoints."""

from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/users/{user_id}/profile")
def get_profile(user_id: str, repo: Repository = Depends(protected_repo)):
    """Return the user profile, or a stub indicating onboarding is needed."""
    profile = repo.get_user_profile(user_id)
    if not profile:
        return {"onboarded": False}
    data = profile.model_dump()
    data["onboarded"] = True
    return data
