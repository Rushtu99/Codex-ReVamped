import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Cpu, ExternalLink, Gauge, Play, RefreshCw, RotateCcw, Search } from "lucide-react";

import { AlertMessage } from "@/components/alert-message";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAccountMutations } from "@/features/accounts/hooks/use-accounts";
import { DashboardSkeleton } from "@/features/dashboard/components/dashboard-skeleton";
import { RequestFilters } from "@/features/dashboard/components/filters/request-filters";
import { LocalModelsPanel } from "@/features/dashboard/components/local-models-panel";
import { RecentRequestsTable } from "@/features/dashboard/components/recent-requests-table";
import { StatsGrid } from "@/features/dashboard/components/stats-grid";
import { useDashboard } from "@/features/dashboard/hooks/use-dashboard";
import { useRequestLogs } from "@/features/dashboard/hooks/use-request-logs";
import type { AccountRollingUsage, AccountSummary } from "@/features/dashboard/schemas";
import { buildDashboardView } from "@/features/dashboard/utils";
import { useLocalModels } from "@/features/local-models/hooks/use-local-models";
import { usePrivacyStore } from "@/hooks/use-privacy";
import { useThemeStore } from "@/hooks/use-theme";
import { cn } from "@/lib/utils";
import {
  buildDuplicateAccountIdSet,
  formatAccountNickname,
  formatCompactAccountId,
} from "@/utils/account-identifiers";
import { normalizeStatus, quotaBarColor, quotaBarTrack } from "@/utils/account-status";
import { REQUEST_STATUS_LABELS, STATUS_LABELS } from "@/utils/constants";
import { formatCompactNumber, formatModelLabel, formatSlug } from "@/utils/formatters";

const MODEL_OPTION_DELIMITER = ":::";
const EMPTY_ROLLING_USAGE: AccountRollingUsage = {
  last5m: { requestCount: 0, totalTokens: 0 },
  last15m: { requestCount: 0, totalTokens: 0 },
  last1h: { requestCount: 0, totalTokens: 0 },
  last1d: { requestCount: 0, totalTokens: 0 },
};
const ROLLING_USAGE_WINDOWS: Array<{ key: keyof AccountRollingUsage; label: string }> = [
  { key: "last5m", label: "5m" },
  { key: "last15m", label: "15m" },
  { key: "last1h", label: "1h" },
  { key: "last1d", label: "1d" },
];

type DashboardAccountAction = "details" | "resume" | "reauth";
type DashboardAccountSort = "risk" | "name" | "weekly" | "last1d";

function accountRiskRank(account: AccountSummary): number {
  const status = normalizeStatus(account.status);
  const primary = account.usage?.primaryRemainingPercent ?? 100;
  const secondary = account.usage?.secondaryRemainingPercent ?? 100;
  const lowest = Math.min(primary, secondary);
  if (status === "deactivated") return 0;
  if (status === "exceeded") return 1;
  if (status === "limited") return 2;
  if (lowest <= 20) return 3;
  if (lowest <= 45) return 4;
  if (status === "paused") return 5;
  return 6;
}

type DashboardAccountRowProps = {
  account: AccountSummary;
  rollingUsage: AccountRollingUsage;
  showAccountId: boolean;
  onAction: (account: AccountSummary, action: DashboardAccountAction) => void;
  busy?: boolean;
};

function DashboardAccountRow({
  account,
  rollingUsage,
  showAccountId,
  onAction,
  busy = false,
}: DashboardAccountRowProps) {
  const blurred = usePrivacyStore((s) => s.blurred);
  const status = normalizeStatus(account.status);
  const title = formatAccountNickname(account);
  const emailSubtitle =
    account.displayName && account.displayName !== account.email ? account.email : null;
  const secondary = account.usage?.secondaryRemainingPercent ?? null;
  const action = status === "paused" ? "resume" : status === "deactivated" ? "reauth" : "details";
  const actionLabel = action === "resume" ? "Resume" : action === "reauth" ? "Re-auth" : "Details";
  const actionIcon = action === "resume" ? Play : action === "reauth" ? RotateCcw : ExternalLink;
  const ActionIcon = actionIcon;
  const secondaryPercent = Math.max(0, Math.min(100, secondary ?? 0));

  return (
    <div className="rounded-lg border bg-card px-3 py-2.5 transition-colors hover:bg-muted/35">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => onAction(account, "details")}
          className="min-w-0 flex-1 text-left"
        >
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-sm font-medium">
                {blurred && emailSubtitle ? <span className="privacy-blur">{title}</span> : title}
              </p>
              <span className="shrink-0 rounded-md border bg-muted/40 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                {formatSlug(account.planType)}
              </span>
            </div>
            <p className="truncate text-xs text-muted-foreground" title={account.email}>
              <span className={blurred && emailSubtitle ? "privacy-blur" : undefined}>
                {emailSubtitle ?? formatSlug(account.planType)}
              </span>
            </p>
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span className="tabular-nums">
                {secondary !== null ? `${secondary}% weekly` : "Weekly n/a"}
              </span>
              <span className="text-muted-foreground/40">•</span>
              <span>
                {showAccountId
                  ? `ID ${formatCompactAccountId(account.accountId, 6, 4)}`
                  : formatCompactAccountId(account.accountId, 6, 4)}
              </span>
            </div>
            <div className={cn("h-1 w-full overflow-hidden rounded-full", quotaBarTrack(secondaryPercent))}>
              <div
                className={cn("h-full rounded-full", quotaBarColor(secondaryPercent))}
                style={{ width: `${secondaryPercent}%` }}
              />
            </div>
          </div>
        </button>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <StatusBadge status={status} />
          <Button
            type="button"
            size="sm"
            variant={action === "resume" ? "default" : "outline"}
            className="h-8 gap-1.5 rounded-md px-3 text-xs"
            onClick={() => onAction(account, action)}
            disabled={busy}
          >
            <ActionIcon className="h-3.5 w-3.5" />
            {actionLabel}
          </Button>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap gap-1.5 border-t pt-2.5">
        {ROLLING_USAGE_WINDOWS.map((window) => {
          const usage = rollingUsage[window.key];
          return (
            <span
              key={`${account.accountId}-${String(window.key)}`}
              className="inline-flex items-center gap-1 rounded-md border bg-muted/35 px-2 py-1 text-[11px] text-muted-foreground"
            >
              <span className="font-semibold text-foreground">{window.label}</span>
              <span>{formatCompactNumber(usage.requestCount)} req</span>
              <span className="text-muted-foreground/45">•</span>
              <span>{formatCompactNumber(usage.totalTokens)} tok</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isDark = useThemeStore((s) => s.theme === "dark");
  const dashboardQuery = useDashboard();
  const { filters, logsQuery, optionsQuery, updateFilters } = useRequestLogs();
  const { metricsQuery } = useLocalModels();
  const { resumeMutation } = useAccountMutations();
  const [accountSearch, setAccountSearch] = useState("");
  const [accountStatusFilter, setAccountStatusFilter] = useState<string>("all");
  const [accountPlanFilter, setAccountPlanFilter] = useState<string>("all");
  const [accountSort, setAccountSort] = useState<DashboardAccountSort>("risk");

  const isRefreshing = dashboardQuery.isFetching || logsQuery.isFetching || metricsQuery.isFetching;

  const handleRefresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }, [queryClient]);

  const handleAccountAction = useCallback(
    (account: AccountSummary, action: DashboardAccountAction) => {
      switch (action) {
        case "details":
          navigate(`/accounts?selected=${account.accountId}`);
          break;
        case "resume":
          void resumeMutation.mutateAsync(account.accountId);
          break;
        case "reauth":
          navigate(`/accounts?selected=${account.accountId}`);
          break;
      }
    },
    [navigate, resumeMutation],
  );

  const overview = dashboardQuery.data;
  const logPage = logsQuery.data;

  const view = useMemo(() => {
    if (!overview || !logPage) {
      return null;
    }
    return buildDashboardView(overview, logPage.requests, isDark);
  }, [overview, logPage, isDark]);

  const statsWithLocal = useMemo(() => {
    if (!view) {
      return [];
    }
    const localTps = metricsQuery.data?.localTps ?? 0;
    const quotaSavedTokens = metricsQuery.data?.quotaSavedTokens ?? 0;
    const quotaSavedPercent = metricsQuery.data?.quotaSavedPercent ?? 0;
    const queueDepth = metricsQuery.data?.queueDepth ?? 0;
    return [
      ...view.stats,
      {
        label: "Local t/s",
        value: localTps.toFixed(2),
        meta: `Queue depth ${formatCompactNumber(queueDepth)}`,
        icon: Gauge,
        trend: [],
        trendColor: "#0ea5e9",
      },
      {
        label: "Quota Saved",
        value: formatCompactNumber(quotaSavedTokens),
        meta: `${quotaSavedPercent.toFixed(1)}% local this session`,
        icon: Cpu,
        trend: [],
        trendColor: "#8b5cf6",
      },
    ];
  }, [view, metricsQuery.data]);

  const healthBoard = useMemo(() => {
    const accounts = [...(overview?.accounts ?? [])];
    const statusCounts = {
      active: 0,
      warning: 0,
      limited: 0,
      deactivated: 0,
    };

    for (const account of accounts) {
      const status = normalizeStatus(account.status);
      const remaining = Math.min(
        account.usage?.primaryRemainingPercent ?? 100,
        account.usage?.secondaryRemainingPercent ?? 100,
      );

      if (status === "deactivated" || status === "exceeded") {
        statusCounts.deactivated += 1;
      } else if (status === "limited") {
        statusCounts.limited += 1;
      } else if (remaining <= 45 || status === "paused") {
        statusCounts.warning += 1;
      } else {
        statusCounts.active += 1;
      }
    }

    accounts.sort((left, right) => {
      const risk = accountRiskRank(left) - accountRiskRank(right);
      if (risk !== 0) {
        return risk;
      }
      const leftRemaining = Math.min(
        left.usage?.primaryRemainingPercent ?? 100,
        left.usage?.secondaryRemainingPercent ?? 100,
      );
      const rightRemaining = Math.min(
        right.usage?.primaryRemainingPercent ?? 100,
        right.usage?.secondaryRemainingPercent ?? 100,
      );
      return leftRemaining - rightRemaining;
    });

    return {
      accounts,
      statusCounts,
    };
  }, [overview?.accounts]);

  const duplicateAccountIds = useMemo(
    () => buildDuplicateAccountIdSet(overview?.accounts ?? []),
    [overview?.accounts],
  );

  const accountStatusOptions = useMemo(() => {
    const options = new Set<string>();
    for (const account of overview?.accounts ?? []) {
      options.add(normalizeStatus(account.status));
    }
    return ["all", ...Array.from(options)];
  }, [overview?.accounts]);

  const accountPlanOptions = useMemo(() => {
    const options = new Set<string>();
    for (const account of overview?.accounts ?? []) {
      if (account.planType) {
        options.add(account.planType);
      }
    }
    return ["all", ...Array.from(options).sort()];
  }, [overview?.accounts]);

  const filteredAccounts = useMemo(() => {
    const rollingUsage = overview?.accountRollingUsage ?? {};
    const needle = accountSearch.trim().toLowerCase();
    const filtered = healthBoard.accounts.filter((account) => {
      const normalizedStatus = normalizeStatus(account.status);
      if (accountStatusFilter !== "all" && normalizedStatus !== accountStatusFilter) {
        return false;
      }
      if (accountPlanFilter !== "all" && account.planType !== accountPlanFilter) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return (
        account.email.toLowerCase().includes(needle) ||
        account.displayName.toLowerCase().includes(needle) ||
        account.accountId.toLowerCase().includes(needle) ||
        account.planType.toLowerCase().includes(needle)
      );
    });

    filtered.sort((left, right) => {
      if (accountSort === "risk") {
        const risk = accountRiskRank(left) - accountRiskRank(right);
        if (risk !== 0) {
          return risk;
        }
        const leftRemaining = left.usage?.secondaryRemainingPercent ?? 101;
        const rightRemaining = right.usage?.secondaryRemainingPercent ?? 101;
        return leftRemaining - rightRemaining;
      }
      if (accountSort === "name") {
        return formatAccountNickname(left).localeCompare(formatAccountNickname(right));
      }
      if (accountSort === "weekly") {
        const leftRemaining = left.usage?.secondaryRemainingPercent ?? 101;
        const rightRemaining = right.usage?.secondaryRemainingPercent ?? 101;
        return leftRemaining - rightRemaining;
      }
      const leftReq = rollingUsage[left.accountId]?.last1d?.requestCount ?? 0;
      const rightReq = rollingUsage[right.accountId]?.last1d?.requestCount ?? 0;
      if (rightReq !== leftReq) {
        return rightReq - leftReq;
      }
      return formatAccountNickname(left).localeCompare(formatAccountNickname(right));
    });

    return filtered;
  }, [
    accountSearch,
    accountStatusFilter,
    accountPlanFilter,
    accountSort,
    healthBoard.accounts,
    overview?.accountRollingUsage,
  ]);

  const accountOptions = useMemo(() => {
    const entries = new Map<string, { label: string; isEmail: boolean }>();
    for (const account of overview?.accounts ?? []) {
      const raw = account.displayName || account.email || account.accountId;
      const isEmail = !!account.email && raw === account.email;
      entries.set(account.accountId, { label: raw, isEmail });
    }
    return (optionsQuery.data?.accountIds ?? []).map((accountId) => {
      const entry = entries.get(accountId);
      return {
        value: accountId,
        label: entry?.label ?? accountId,
        isEmail: entry?.isEmail ?? false,
      };
    });
  }, [optionsQuery.data?.accountIds, overview?.accounts]);

  const modelOptions = useMemo(
    () =>
      (optionsQuery.data?.modelOptions ?? []).map((option) => ({
        value: `${option.model}${MODEL_OPTION_DELIMITER}${option.reasoningEffort ?? ""}`,
        label: formatModelLabel(option.model, option.reasoningEffort),
      })),
    [optionsQuery.data?.modelOptions],
  );

  const statusOptions = useMemo(
    () =>
      (optionsQuery.data?.statuses ?? []).map((status) => ({
        value: status,
        label: REQUEST_STATUS_LABELS[status] ?? formatSlug(status),
      })),
    [optionsQuery.data?.statuses],
  );

  const sourceOptions = useMemo(
    () =>
      (optionsQuery.data?.sources ?? ["cloud"]).map((source) => ({
        value: source,
        label: source === "local" ? "⚡ Local" : "☁ Cloud",
      })),
    [optionsQuery.data?.sources],
  );

  const errorMessage =
    (dashboardQuery.error instanceof Error && dashboardQuery.error.message) ||
    (logsQuery.error instanceof Error && logsQuery.error.message) ||
    (metricsQuery.error instanceof Error && metricsQuery.error.message) ||
    (optionsQuery.error instanceof Error && optionsQuery.error.message) ||
    null;

  return (
    <div className="animate-fade-in-up space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">CodexLB ReVamped</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Account health first, quota risk second, request traffic underneath.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
          title="Refresh dashboard"
        >
          <RefreshCw className={`h-4 w-4${isRefreshing ? " animate-spin" : ""}`} />
        </button>
      </div>

      {errorMessage ? <AlertMessage variant="error">{errorMessage}</AlertMessage> : null}

      {!view ? (
        <DashboardSkeleton />
      ) : (
        <>
          <section className="rounded-md border bg-card px-4 py-3" data-testid="account-health-summary">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold">Healthy / Watchlist / Limited / Action</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">Pool state snapshot</p>
              </div>
              <p className="font-mono text-2xl font-semibold tracking-tight">
                <span className="text-emerald-500">{healthBoard.statusCounts.active}</span>
                <span className="px-1 text-muted-foreground/60">/</span>
                <span className="text-amber-500">{healthBoard.statusCounts.warning}</span>
                <span className="px-1 text-muted-foreground/60">/</span>
                <span className="text-orange-500">{healthBoard.statusCounts.limited}</span>
                <span className="px-1 text-muted-foreground/60">/</span>
                <span className="text-red-500">{healthBoard.statusCounts.deactivated}</span>
              </p>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
              <span>
                <span className="font-semibold text-emerald-500">H</span> Healthy
              </span>
              <span>
                <span className="font-semibold text-amber-500">W</span> Watchlist
              </span>
              <span>
                <span className="font-semibold text-orange-500">L</span> Limited
              </span>
              <span>
                <span className="font-semibold text-red-500">A</span> Action needed
              </span>
              <span className="text-muted-foreground/60">•</span>
              <span>{formatCompactNumber(healthBoard.accounts.length)} accounts</span>
            </div>
          </section>

          <StatsGrid stats={statsWithLocal} />

          <LocalModelsPanel />

          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <h2 className="text-[13px] font-medium uppercase tracking-wider text-muted-foreground">Account</h2>
              <div className="h-px flex-1 bg-border" />
            </div>

            <div className="space-y-3 rounded-xl border bg-card p-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-0 flex-1">
                  <Search
                    className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/60"
                    aria-hidden
                  />
                  <Input
                    placeholder="Search accounts..."
                    value={accountSearch}
                    onChange={(event) => setAccountSearch(event.target.value)}
                    className="h-8 pl-8"
                  />
                </div>
                <Select value={accountStatusFilter} onValueChange={setAccountStatusFilter}>
                  <SelectTrigger size="sm" className="w-36">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    {accountStatusOptions.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option === "all"
                          ? "All statuses"
                          : STATUS_LABELS[option as keyof typeof STATUS_LABELS]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={accountPlanFilter} onValueChange={setAccountPlanFilter}>
                  <SelectTrigger size="sm" className="w-28">
                    <SelectValue placeholder="Plan" />
                  </SelectTrigger>
                  <SelectContent>
                    {accountPlanOptions.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option === "all" ? "All plans" : formatSlug(option)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={accountSort}
                  onValueChange={(value) => setAccountSort(value as DashboardAccountSort)}
                >
                  <SelectTrigger size="sm" className="w-48">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="risk">Sort: Risk</SelectItem>
                    <SelectItem value="name">Sort: Name A-Z</SelectItem>
                    <SelectItem value="weekly">Sort: Weekly remaining low-high</SelectItem>
                    <SelectItem value="last1d">Sort: Last 1d requests high-low</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="max-h-[calc(100vh-22rem)] space-y-1 overflow-y-auto pr-1">
                {filteredAccounts.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 rounded-md border border-dashed p-6 text-center">
                    <p className="text-sm font-medium text-muted-foreground">No matching accounts</p>
                    <p className="text-xs text-muted-foreground/70">Try adjusting your filters.</p>
                  </div>
                ) : (
                  filteredAccounts.map((account) => (
                    <DashboardAccountRow
                      key={account.accountId}
                      account={account}
                      rollingUsage={overview?.accountRollingUsage?.[account.accountId] ?? EMPTY_ROLLING_USAGE}
                      showAccountId={duplicateAccountIds.has(account.accountId)}
                      onAction={handleAccountAction}
                      busy={resumeMutation.isPending}
                    />
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <h2 className="text-[13px] font-medium uppercase tracking-wider text-muted-foreground">
                Request traffic
              </h2>
              <div className="h-px flex-1 bg-border" />
            </div>
            <RequestFilters
              filters={filters}
              accountOptions={accountOptions}
              modelOptions={modelOptions}
              statusOptions={statusOptions}
              sourceOptions={sourceOptions}
              onSearchChange={(search) => updateFilters({ search, offset: 0 })}
              onTimeframeChange={(timeframe) => updateFilters({ timeframe, offset: 0 })}
              onAccountChange={(accountIds) => updateFilters({ accountIds, offset: 0 })}
              onModelChange={(modelOptionsSelected) =>
                updateFilters({ modelOptions: modelOptionsSelected, offset: 0 })
              }
              onStatusChange={(statuses) => updateFilters({ statuses, offset: 0 })}
              onSourceChange={(sources) => updateFilters({ sources, offset: 0 })}
              onReset={() =>
                updateFilters({
                  search: "",
                  timeframe: "all",
                  accountIds: [],
                  modelOptions: [],
                  statuses: [],
                  sources: [],
                  offset: 0,
                })
              }
            />
            <div className="transition-opacity duration-200">
              <RecentRequestsTable
                requests={view.requestLogs}
                accounts={overview?.accounts ?? []}
                total={logPage?.total ?? 0}
                limit={filters.limit}
                offset={filters.offset}
                hasMore={logPage?.hasMore ?? false}
                onLimitChange={(limit) => updateFilters({ limit, offset: 0 })}
                onOffsetChange={(offset) => updateFilters({ offset })}
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
