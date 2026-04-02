import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldCheck, ShieldX, Zap } from "lucide-react";

import { AlertMessage } from "@/components/alert-message";
import { useAccountMutations } from "@/features/accounts/hooks/use-accounts";
import { AccountCards } from "@/features/dashboard/components/account-cards";
import { DashboardSkeleton } from "@/features/dashboard/components/dashboard-skeleton";
import { RequestFilters } from "@/features/dashboard/components/filters/request-filters";
import { RecentRequestsTable } from "@/features/dashboard/components/recent-requests-table";
import { StatsGrid } from "@/features/dashboard/components/stats-grid";
import { UsageDonuts } from "@/features/dashboard/components/usage-donuts";
import { useDashboard } from "@/features/dashboard/hooks/use-dashboard";
import { useRequestLogs } from "@/features/dashboard/hooks/use-request-logs";
import { buildDashboardView } from "@/features/dashboard/utils";
import type { AccountSummary } from "@/features/dashboard/schemas";
import { useThemeStore } from "@/hooks/use-theme";
import { REQUEST_STATUS_LABELS } from "@/utils/constants";
import { formatAccountNickname } from "@/utils/account-identifiers";
import { formatModelLabel, formatSlug } from "@/utils/formatters";
import { normalizeStatus } from "@/utils/account-status";

const MODEL_OPTION_DELIMITER = ":::";

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isDark = useThemeStore((s) => s.theme === "dark");
  const dashboardQuery = useDashboard();
  const { filters, logsQuery, optionsQuery, updateFilters } = useRequestLogs();
  const { pauseMutation, resumeMutation } = useAccountMutations();

  const isRefreshing = dashboardQuery.isFetching || logsQuery.isFetching;

  const handleRefresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }, [queryClient]);

  const handleAccountAction = useCallback(
    (account: AccountSummary, action: string) => {
      switch (action) {
        case "details":
          navigate(`/accounts?selected=${account.accountId}`);
          break;
        case "resume":
          void resumeMutation.mutateAsync(account.accountId);
          break;
        case "pause":
          void pauseMutation.mutateAsync(account.accountId);
          break;
        case "reauth":
          navigate(`/accounts?selected=${account.accountId}`);
          break;
      }
    },
    [navigate, pauseMutation, resumeMutation],
  );

  const overview = dashboardQuery.data;
  const logPage = logsQuery.data;

  const view = useMemo(() => {
    if (!overview || !logPage) {
      return null;
    }
    return buildDashboardView(overview, logPage.requests, isDark);
  }, [overview, logPage, isDark]);

  const healthBoard = useMemo(() => {
    const accounts = [...(overview?.accounts ?? [])];
    const statusCounts = {
      active: 0,
      warning: 0,
      limited: 0,
      deactivated: 0,
    };

    const rank = (account: AccountSummary) => {
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
      const risk = rank(left) - rank(right);
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

  const accountOptions = useMemo(() => {
    const entries = new Map<string, { label: string; isEmail: boolean }>();
    for (const account of overview?.accounts ?? []) {
      const label = formatAccountNickname(account);
      entries.set(account.accountId, { label, isEmail: false });
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

  const errorMessage =
    (dashboardQuery.error instanceof Error && dashboardQuery.error.message) ||
    (logsQuery.error instanceof Error && logsQuery.error.message) ||
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
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-md border bg-card px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                Healthy
              </div>
              <p className="mt-2 text-2xl font-semibold">{healthBoard.statusCounts.active}</p>
            </div>
            <div className="rounded-md border bg-card px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                Watchlist
              </div>
              <p className="mt-2 text-2xl font-semibold">{healthBoard.statusCounts.warning}</p>
            </div>
            <div className="rounded-md border bg-card px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <Zap className="h-3.5 w-3.5 text-orange-500" />
                Limited
              </div>
              <p className="mt-2 text-2xl font-semibold">{healthBoard.statusCounts.limited}</p>
            </div>
            <div className="rounded-md border bg-card px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <ShieldX className="h-3.5 w-3.5 text-red-500" />
                Action needed
              </div>
              <p className="mt-2 text-2xl font-semibold">{healthBoard.statusCounts.deactivated}</p>
            </div>
          </section>

          <StatsGrid stats={view.stats} />

          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <h2 className="text-[13px] font-medium uppercase tracking-wider text-muted-foreground">Account health</h2>
              <div className="h-px flex-1 bg-border" />
            </div>
            <AccountCards accounts={healthBoard.accounts} onAction={handleAccountAction} />
          </section>

          <UsageDonuts
            primaryItems={view.primaryUsageItems}
            secondaryItems={view.secondaryUsageItems}
            primaryTotal={overview?.summary.primaryWindow.capacityCredits ?? 0}
            secondaryTotal={overview?.summary.secondaryWindow?.capacityCredits ?? 0}
            safeLinePrimary={view.safeLinePrimary}
            safeLineSecondary={view.safeLineSecondary}
          />

          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <h2 className="text-[13px] font-medium uppercase tracking-wider text-muted-foreground">Request traffic</h2>
              <div className="h-px flex-1 bg-border" />
            </div>
            <RequestFilters
              filters={filters}
              accountOptions={accountOptions}
              modelOptions={modelOptions}
              statusOptions={statusOptions}
              onSearchChange={(search) => updateFilters({ search, offset: 0 })}
              onTimeframeChange={(timeframe) => updateFilters({ timeframe, offset: 0 })}
              onAccountChange={(accountIds) => updateFilters({ accountIds, offset: 0 })}
              onModelChange={(modelOptionsSelected) =>
                updateFilters({ modelOptions: modelOptionsSelected, offset: 0 })
              }
              onStatusChange={(statuses) => updateFilters({ statuses, offset: 0 })}
              onReset={() =>
                updateFilters({
                  search: "",
                  timeframe: "all",
                  accountIds: [],
                  modelOptions: [],
                  statuses: [],
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
