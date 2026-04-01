from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import Protocol, ProtocolCreate, ProtocolUpdate, ProtocolExecution, ProtocolExecutionCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/protocols", tags=["protocols"])


@router.post("", response_model=Protocol)
def create_protocol(payload: ProtocolCreate, repo: Repository = Depends(protected_repo)) -> Protocol:
    return repo.create_protocol(payload)


@router.get("", response_model=list[Protocol])
def list_protocols(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[Protocol]:
    return repo.list_protocols(user_id=user_id, limit=limit, offset=offset)


@router.get("/{protocol_id}", response_model=Protocol)
def get_protocol(protocol_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> Protocol:
    protocol = repo.get_protocol(protocol_id=protocol_id, user_id=user_id)
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")
    return protocol


@router.put("/{protocol_id}", response_model=Protocol)
def update_protocol(
    protocol_id: str, user_id: str, payload: ProtocolUpdate,
    repo: Repository = Depends(protected_repo),
) -> Protocol:
    updated = repo.update_protocol(protocol_id=protocol_id, user_id=user_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol not found")
    return updated


@router.post("/{protocol_id}/executions", response_model=ProtocolExecution)
def create_execution(
    protocol_id: str, payload: ProtocolExecutionCreate,
    repo: Repository = Depends(protected_repo),
) -> ProtocolExecution:
    # Ensure protocol_id in path matches payload
    if payload.protocol_id != protocol_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="protocol_id mismatch")
    return repo.create_protocol_execution(payload)


@router.get("/{protocol_id}/executions", response_model=list[ProtocolExecution])
def list_executions(
    protocol_id: str,
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[ProtocolExecution]:
    return repo.list_protocol_executions(user_id=user_id, protocol_id=protocol_id, limit=limit, offset=offset)
