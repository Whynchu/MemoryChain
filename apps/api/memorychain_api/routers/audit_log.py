from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import AuditLogEntry
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1", tags=["audit-log"])


@router.get("/audit-log", response_model=list[AuditLogEntry])
def list_audit_log(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[AuditLogEntry]:
    return repo.list_audit_logs(user_id=user_id, limit=limit, offset=offset)


@router.post("/audit-log/{audit_log_id}/rollback", response_model=AuditLogEntry)
def rollback_audit_log(
    audit_log_id: str,
    user_id: str,
    repo: Repository = Depends(protected_repo),
) -> AuditLogEntry:
    try:
        rollback_log = repo.rollback_audit_log(user_id=user_id, audit_log_id=audit_log_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if rollback_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return rollback_log
