from datetime import date

from fastapi import APIRouter, Depends, Query

from ..dependencies import protected_repo
from ..schemas import SearchObjectType, SearchResponse
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    user_id: str,
    q: str | None = None,
    type: list[SearchObjectType] | None = Query(default=None),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    tag: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    repo: Repository = Depends(protected_repo),
) -> SearchResponse:
    results = repo.search(
        user_id=user_id,
        query=q,
        object_types=type,
        date_from=from_date,
        date_to=to_date,
        tag=tag,
        limit=limit,
    )
    return SearchResponse(results=results)
