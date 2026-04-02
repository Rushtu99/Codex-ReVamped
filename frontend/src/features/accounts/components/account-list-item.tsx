import { Pause, Play } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePrivacyStore } from "@/hooks/use-privacy";
import type { AccountSummary } from "@/features/accounts/schemas";
import { normalizeStatus, quotaBarColor, quotaBarTrack } from "@/utils/account-status";
import { formatAccountNickname, formatCompactAccountId } from "@/utils/account-identifiers";
import { formatSlug } from "@/utils/formatters";

export type AccountListItemProps = {
  account: AccountSummary;
  selected: boolean;
  showAccountId?: boolean;
  onSelect: (accountId: string) => void;
  onPause: (accountId: string) => void;
  onResume: (accountId: string) => void;
  onReauth: (accountId: string) => void;
  busy?: boolean;
};

function MiniQuotaBar({ percent }: { percent: number | null }) {
  if (percent === null) {
    return <div data-testid="mini-quota-track" className="h-1 flex-1 overflow-hidden rounded-full bg-muted" />;
  }
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div data-testid="mini-quota-track" className={cn("h-1 flex-1 overflow-hidden rounded-full", quotaBarTrack(clamped))}>
      <div
        data-testid="mini-quota-fill"
        className={cn("h-full rounded-full", quotaBarColor(clamped))}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function AccountListItem({
  account,
  selected,
  showAccountId = false,
  onSelect,
  onPause,
  onResume,
  onReauth,
  busy = false,
}: AccountListItemProps) {
  const blurred = usePrivacyStore((s) => s.blurred);
  const status = normalizeStatus(account.status);
  const title = formatAccountNickname(account);
  const emailSubtitle = account.displayName && account.displayName !== account.email
    ? account.email
    : null;
  const baseSubtitle = emailSubtitle ?? formatSlug(account.planType);
  const secondary = account.usage?.secondaryRemainingPercent ?? null;
  const actionLabel = status === "paused" ? "Resume" : status === "deactivated" ? "Re-auth" : "Pause";
  const actionIcon = status === "paused" ? Play : Pause;
  const actionHandler = status === "paused" ? onResume : status === "deactivated" ? onReauth : onPause;
  const ActionIcon = actionIcon;

  return (
    <div
      className={cn(
        "w-full rounded-lg border bg-card px-3 py-2.5 transition-colors",
        selected ? "border-primary/30 bg-primary/6" : "hover:bg-muted/40",
      )}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => onSelect(account.accountId)}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex min-w-0 items-start gap-2.5">
            <div className="min-w-0 flex-1 space-y-1">
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
                  {emailSubtitle ?? baseSubtitle}
                </span>
              </p>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <span className="tabular-nums">{secondary !== null ? `${secondary}% weekly` : "Weekly n/a"}</span>
                <span className="text-muted-foreground/40">•</span>
                <span>{showAccountId ? `ID ${formatCompactAccountId(account.accountId, 6, 4)}` : formatCompactAccountId(account.accountId, 6, 4)}</span>
              </div>
              <div className="pt-0.5">
                <MiniQuotaBar percent={secondary} />
              </div>
            </div>
          </div>
        </button>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <StatusBadge status={status} />
          <Button
            type="button"
            size="sm"
            variant={status === "paused" ? "default" : "outline"}
            className="h-8 gap-1.5 rounded-md px-3 text-xs"
            onClick={() => actionHandler(account.accountId)}
            disabled={busy}
          >
            <ActionIcon className="h-3.5 w-3.5" />
            {actionLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
