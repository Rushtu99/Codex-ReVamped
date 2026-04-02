from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.shared.schemas import DashboardModel

OmxAction = Literal[
    "version",
    "status",
    "doctor",
    "doctor_team",
    "cleanup",
    "cleanup_dry_run",
    "cancel",
    "reasoning_get",
    "reasoning_set",
]
OmxReasoningLevel = Literal["low", "medium", "high", "xhigh"]


class OmxOverviewResponse(DashboardModel):
    available: bool
    binary_path: str | None = None
    runtime_env_path: str | None = None
    runtime_dir: str | None = None
    version: str | None = None
    reasoning: OmxReasoningLevel | None = None
    status_summary: str | None = None
    doctor_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    last_checked_at: datetime


class OmxQuickRef(DashboardModel):
    key: str
    label: str
    command: str
    description: str


class OmxDashboardSession(DashboardModel):
    id: str
    status: str
    context_line: str
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    cwd: str | None = None
    source: str


class OmxDashboardWorker(DashboardModel):
    team: str
    worker_id: str
    status: str
    job_line: str
    role: str | None = None
    last_heartbeat_at: datetime | None = None
    session_id: str | None = None


class OmxSessionTokenUsage(DashboardModel):
    session_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    exact: bool = False


class OmxWorkerTokenUsage(DashboardModel):
    team: str
    worker_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    exact: bool = False


class OmxTokenUsage(DashboardModel):
    sessions: list[OmxSessionTokenUsage] = Field(default_factory=list)
    workers: list[OmxWorkerTokenUsage] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OmxDashboardResponse(DashboardModel):
    quick_refs: list[OmxQuickRef] = Field(default_factory=list)
    sessions: list[OmxDashboardSession] = Field(default_factory=list)
    workers: list[OmxDashboardWorker] = Field(default_factory=list)
    token_usage: OmxTokenUsage = Field(default_factory=OmxTokenUsage)
    warnings: list[str] = Field(default_factory=list)
    updated_at: datetime


class OmxRunRequest(DashboardModel):
    action: OmxAction
    level: OmxReasoningLevel | None = None


class OmxCommandResultResponse(DashboardModel):
    action: OmxAction
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
    timed_out: bool = False
