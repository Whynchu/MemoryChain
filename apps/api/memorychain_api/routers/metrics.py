from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import protected_repo
from ..schemas import MetricObservation, MetricObservationCreate
from ..storage.repository import Repository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.post("", response_model=MetricObservation)
def create_metric(payload: MetricObservationCreate, repo: Repository = Depends(protected_repo)) -> MetricObservation:
    return repo.create_metric_observation(payload)


@router.get("", response_model=list[MetricObservation])
def list_metrics(
    user_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    repo: Repository = Depends(protected_repo),
) -> list[MetricObservation]:
    return repo.list_metric_observations(user_id=user_id, limit=limit, offset=offset)


@router.get("/{metric_id}", response_model=MetricObservation)
def get_metric(metric_id: str, user_id: str, repo: Repository = Depends(protected_repo)) -> MetricObservation:
    metric = repo.get_metric_observation(metric_id=metric_id, user_id=user_id)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric observation not found")
    return metric
