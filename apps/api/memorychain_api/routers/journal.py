from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import JournalEntry
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/journal-entries", tags=["journal-entries"])


@router.get("", response_model=list[JournalEntry])
def list_journal_entries(user_id: str, repo: Repository = Depends(protected_repo)) -> list[JournalEntry]:
    return repo.list_journal_entries(user_id)
