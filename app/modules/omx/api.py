from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth.dependencies import set_dashboard_error_format, validate_dashboard_session
from app.core.exceptions import DashboardBadRequestError
from app.modules.omx.schemas import (
    OmxCommandResultResponse,
    OmxDashboardResponse,
    OmxOverviewResponse,
    OmxRunRequest,
)
from app.modules.omx.service import OmxService

router = APIRouter(
    prefix="/api/omx",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


@router.get("/overview", response_model=OmxOverviewResponse)
async def get_omx_overview() -> OmxOverviewResponse:
    service = OmxService()
    return await service.get_overview()


@router.get("/dashboard", response_model=OmxDashboardResponse)
async def get_omx_dashboard() -> OmxDashboardResponse:
    service = OmxService()
    return await service.get_dashboard()


@router.post("/run", response_model=OmxCommandResultResponse)
async def run_omx_command(payload: OmxRunRequest) -> OmxCommandResultResponse:
    if payload.action == "reasoning_set" and payload.level is None:
        raise DashboardBadRequestError("`level` is required for reasoning_set.", code="invalid_payload")

    service = OmxService()
    return await service.run_action(payload.action, level=payload.level)
