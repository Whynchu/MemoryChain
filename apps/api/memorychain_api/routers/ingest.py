from fastapi import APIRouter, Depends

from ..dependencies import protected_repo
from ..schemas import IngestRequest, IngestResponse
from ..services.ingestion import ingest
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(payload: IngestRequest, repo: Repository = Depends(protected_repo)) -> IngestResponse:
    return ingest(repo, payload)
