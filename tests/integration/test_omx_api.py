from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.omx.schemas import (
    OmxCommandResultResponse,
    OmxDashboardResponse,
    OmxDashboardSession,
    OmxDashboardWorker,
    OmxOverviewResponse,
    OmxQuickRef,
    OmxSessionTokenUsage,
    OmxTokenUsage,
    OmxWorkerTokenUsage,
)
from app.modules.omx.service import OmxService

pytestmark = pytest.mark.integration


def test_omx_overview_and_dashboard_routes_registered(app_instance):
    route_paths = {getattr(route, "path", "") for route in app_instance.router.routes}
    assert "/api/omx/overview" in route_paths
    assert "/api/omx/dashboard" in route_paths


@pytest.mark.asyncio
async def test_omx_overview_endpoint(async_client, monkeypatch):
    async def fake_overview(self):
        return OmxOverviewResponse(
            available=True,
            binary_path="/tmp/omx",
            runtime_env_path="/tmp/runtime.env",
            runtime_dir="/tmp",
            version="oh-my-codex v0.0.0",
            reasoning="high",
            status_summary="No active modes.",
            doctor_summary="All checks passed.",
            warnings=[],
            last_checked_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OmxService, "get_overview", fake_overview)

    response = await async_client.get("/api/omx/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["version"] == "oh-my-codex v0.0.0"


@pytest.mark.asyncio
async def test_omx_dashboard_endpoint(async_client, monkeypatch):
    async def fake_dashboard(self):
        return OmxDashboardResponse(
            quick_refs=[
                OmxQuickRef(
                    key="team",
                    label="Team Mode",
                    command='$team 3 "implement"',
                    description="Start coordinated team mode.",
                )
            ],
            sessions=[
                OmxDashboardSession(
                    id="omx-session-1",
                    status="running",
                    context_line="cwd /tmp · pid 123",
                    started_at=datetime.now(UTC),
                    last_activity_at=datetime.now(UTC),
                    cwd="/tmp",
                    source="state",
                )
            ],
            workers=[
                OmxDashboardWorker(
                    team="demo-team",
                    worker_id="worker-1",
                    status="in_progress",
                    job_line="Implement OMX session panel",
                    role="executor",
                    last_heartbeat_at=datetime.now(UTC),
                    session_id="worker-session-1",
                )
            ],
            token_usage=OmxTokenUsage(
                sessions=[
                    OmxSessionTokenUsage(
                        session_id="omx-session-1",
                        input_tokens=10,
                        output_tokens=20,
                        total_tokens=30,
                        exact=True,
                    )
                ],
                workers=[OmxWorkerTokenUsage(team="demo-team", worker_id="worker-1", exact=False)],
                notes=["Worker token metrics unavailable."],
            ),
            warnings=[],
            updated_at=datetime.now(UTC),
        )

    monkeypatch.setattr(OmxService, "get_dashboard", fake_dashboard)

    response = await async_client.get("/api/omx/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["quickRefs"][0]["key"] == "team"
    assert payload["sessions"][0]["id"] == "omx-session-1"
    assert payload["workers"][0]["workerId"] == "worker-1"
    assert payload["tokenUsage"]["sessions"][0]["totalTokens"] == 30


@pytest.mark.asyncio
async def test_omx_run_requires_level_for_reasoning_set(async_client):
    response = await async_client.post("/api/omx/run", json={"action": "reasoning_set"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_payload"


@pytest.mark.asyncio
async def test_omx_run_status(async_client, monkeypatch):
    async def fake_run(self, action, level=None):
        _ = level
        return OmxCommandResultResponse(
            action=action,
            command=["omx", "status"],
            exit_code=0,
            stdout="No active modes.",
            stderr="",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            timed_out=False,
        )

    monkeypatch.setattr(OmxService, "run_action", fake_run)

    response = await async_client.post("/api/omx/run", json={"action": "status"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["exitCode"] == 0
    assert payload["stdout"] == "No active modes."
