from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.modules.shared.schemas import DashboardModel


class LocalModelStatusResponse(DashboardModel):
    bridge_running: bool = False
    ollama_running: bool = False
    endpoint: str | None = None
    loaded_count: int = 0


class LocalModelEntry(DashboardModel):
    name: str
    digest: str | None = None
    size_bytes: int = 0
    modified_at: datetime | None = None
    loaded: bool = False
    loaded_size_bytes: int = 0
    last_used_at: datetime | None = None


class LocalModelListResponse(DashboardModel):
    models: list[LocalModelEntry] = Field(default_factory=list)


class LocalModelMetricsResponse(DashboardModel):
    local_tps: float = 0.0
    request_count: int = 0
    queue_depth: int = 0
    quota_saved_tokens: int = 0
    quota_saved_percent: float = 0.0
