from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import Field

from app.modules.accounts.schemas import AccountSummary
from app.modules.shared.schemas import DashboardModel
from app.modules.usage.schemas import MetricsTrends, UsageSummaryResponse, UsageWindowResponse


class DashboardUsageWindows(DashboardModel):
    primary: UsageWindowResponse
    secondary: UsageWindowResponse | None = None


class DepletionResponse(DashboardModel):
    risk: float
    risk_level: str  # "safe" | "warning" | "danger" | "critical"
    burn_rate: float
    safe_usage_percent: float
    projected_exhaustion_at: datetime | None = None
    seconds_until_exhaustion: float | None = None


class AccountRollingUsageWindow(DashboardModel):
    request_count: int = 0
    total_tokens: int = 0


class AccountRollingUsage(DashboardModel):
    last5m: AccountRollingUsageWindow = Field(default_factory=AccountRollingUsageWindow, alias="last5m")
    last15m: AccountRollingUsageWindow = Field(default_factory=AccountRollingUsageWindow, alias="last15m")
    last1h: AccountRollingUsageWindow = Field(default_factory=AccountRollingUsageWindow, alias="last1h")
    last1d: AccountRollingUsageWindow = Field(default_factory=AccountRollingUsageWindow, alias="last1d")


class DashboardOverviewResponse(DashboardModel):
    last_sync_at: datetime | None = None
    accounts: List[AccountSummary] = Field(default_factory=list)
    account_rolling_usage: dict[str, AccountRollingUsage] = Field(default_factory=dict)
    summary: UsageSummaryResponse
    windows: DashboardUsageWindows
    trends: MetricsTrends
    depletion_primary: DepletionResponse | None = None
    depletion_secondary: DepletionResponse | None = None
