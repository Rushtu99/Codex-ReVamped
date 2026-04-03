from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth.dependencies import set_dashboard_error_format, validate_dashboard_session
from app.modules.local_models.schemas import (
    LocalModelListResponse,
    LocalModelMetricsResponse,
    LocalModelStatusResponse,
)
from app.modules.local_models.service import LocalModelsService

router = APIRouter(
    prefix="/api/local-models",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


def _service() -> LocalModelsService:
    return LocalModelsService()


@router.get("/status", response_model=LocalModelStatusResponse)
async def get_local_model_status(service: LocalModelsService = Depends(_service)) -> LocalModelStatusResponse:
    return await service.status()


@router.get("/models", response_model=LocalModelListResponse)
async def get_local_models(service: LocalModelsService = Depends(_service)) -> LocalModelListResponse:
    return await service.models()


@router.get("/metrics", response_model=LocalModelMetricsResponse)
async def get_local_model_metrics(service: LocalModelsService = Depends(_service)) -> LocalModelMetricsResponse:
    return await service.metrics()
