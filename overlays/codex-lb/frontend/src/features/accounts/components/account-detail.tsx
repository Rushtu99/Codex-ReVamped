import { User } from "lucide-react";

import { usePrivacyStore } from "@/hooks/use-privacy";
import { AccountActions } from "@/features/accounts/components/account-actions";
import { AccountTokenInfo } from "@/features/accounts/components/account-token-info";
import { AccountUsagePanel } from "@/features/accounts/components/account-usage-panel";
import type { AccountSummary } from "@/features/accounts/schemas";
import { useAccountTrends } from "@/features/accounts/hooks/use-accounts";
import { formatAccountNickname, formatCompactAccountId } from "@/utils/account-identifiers";
import { StatusBadge } from "@/components/status-badge";
import { normalizeStatus } from "@/utils/account-status";

export type AccountDetailProps = {
  account: AccountSummary | null;
  showAccountId?: boolean;
  busy: boolean;
  onPause: (accountId: string) => void;
  onResume: (accountId: string) => void;
  onDelete: (accountId: string) => void;
  onReauth: () => void;
};

export function AccountDetail({
  account,
  showAccountId = false,
  busy,
  onPause,
  onResume,
  onDelete,
  onReauth,
}: AccountDetailProps) {
  const { data: trends } = useAccountTrends(account?.accountId ?? null);
  const blurred = usePrivacyStore((s) => s.blurred);

  if (!account) {
    return (
      <div className="flex flex-col items-center justify-center rounded-md border border-dashed p-12">
        <div className="flex h-12 w-12 items-center justify-center rounded-md bg-muted">
          <User className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="mt-3 text-sm font-medium text-muted-foreground">Select an account</p>
        <p className="mt-1 text-xs text-muted-foreground/70">Choose an account from the list to view details.</p>
      </div>
    );
  }

  const title = formatAccountNickname(account);
  const status = normalizeStatus(account.status);
  const compactId = formatCompactAccountId(account.accountId);
  const emailSubtitle = account.displayName && account.displayName !== account.email
    ? account.email
    : null;

  return (
    <div key={account.accountId} className="animate-fade-in-up space-y-4 rounded-md border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <span>{account.planType}</span>
            <span>Account detail</span>
            {showAccountId ? <span>ID {compactId}</span> : null}
          </div>
          <h2 className="truncate text-base font-semibold">
            <span className={blurred && emailSubtitle ? "privacy-blur" : undefined}>{title}</span>
          </h2>
          <p className="mt-0.5 truncate text-xs text-muted-foreground" title={account.email}>
            <span className={blurred && emailSubtitle ? "privacy-blur" : undefined}>
              {emailSubtitle ?? account.email}
            </span>
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <StatusBadge status={status} />
        </div>
      </div>

      <AccountUsagePanel account={account} trends={trends} />
      <AccountTokenInfo account={account} />
      <AccountActions
        account={account}
        busy={busy}
        onPause={onPause}
        onResume={onResume}
        onDelete={onDelete}
        onReauth={onReauth}
      />
    </div>
  );
}
