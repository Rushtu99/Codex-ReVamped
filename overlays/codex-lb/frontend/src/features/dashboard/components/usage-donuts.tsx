import { AlertTriangle, Gauge, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { RemainingItem, SafeLineView } from "@/features/dashboard/utils";
import { formatCompactNumber, formatPercentNullable } from "@/utils/formatters";

export type UsageDonutsProps = {
  primaryItems: RemainingItem[];
  secondaryItems: RemainingItem[];
  primaryTotal: number;
  secondaryTotal: number;
  safeLinePrimary?: SafeLineView | null;
  safeLineSecondary?: SafeLineView | null;
};

function quotaTone(percent: number | null) {
  if (percent == null) {
    return {
      bar: "bg-muted-foreground/30",
      text: "text-muted-foreground",
      rail: "bg-muted",
    };
  }
  if (percent <= 20) {
    return {
      bar: "bg-red-500",
      text: "text-red-500",
      rail: "bg-red-500/15",
    };
  }
  if (percent <= 45) {
    return {
      bar: "bg-amber-500",
      text: "text-amber-500",
      rail: "bg-amber-500/15",
    };
  }
  return {
    bar: "bg-emerald-500",
    text: "text-emerald-500",
    rail: "bg-emerald-500/15",
  };
}

function riskLabel(safeLine?: SafeLineView | null) {
  if (!safeLine) {
    return { label: "Stable", tone: "text-muted-foreground", icon: Gauge };
  }
  if (safeLine.riskLevel === "critical" || safeLine.riskLevel === "danger") {
    return { label: "Exhaustion risk", tone: "text-red-500", icon: ShieldAlert };
  }
  return { label: "Watch depletion", tone: "text-amber-500", icon: AlertTriangle };
}

function QuotaBoard({
  title,
  items,
  total,
  safeLine,
}: {
  title: string;
  items: RemainingItem[];
  total: number;
  safeLine?: SafeLineView | null;
}) {
  const sortedItems = [...items].sort((left, right) => {
    const leftPercent = left.remainingPercent ?? 1000;
    const rightPercent = right.remainingPercent ?? 1000;
    return leftPercent - rightPercent;
  });
  const risk = riskLabel(safeLine);
  const RiskIcon = risk.icon;

  return (
    <section className="rounded-md border bg-card">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Pool remaining {formatCompactNumber(total)}
          </p>
        </div>
        <div className={cn("inline-flex items-center gap-1.5 text-xs font-medium", risk.tone)}>
          <RiskIcon className="h-3.5 w-3.5" />
          {risk.label}
        </div>
      </div>

      <div className="divide-y">
        {sortedItems.map((item) => {
          const percent = item.remainingPercent == null ? null : Math.max(0, Math.min(100, item.remainingPercent));
          const tone = quotaTone(percent);

          return (
            <div key={item.accountId} className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_7rem] md:items-center">
              <div className="min-w-0">
                <div className="flex items-center justify-between gap-3">
                  <p className="truncate text-sm font-medium">
                    {item.label}
                    {item.labelSuffix}
                  </p>
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">
                    {formatCompactNumber(item.value)}
                  </span>
                </div>
                <div className={cn("mt-2 h-1.5 w-full overflow-hidden rounded-full", tone.rail)}>
                  <div
                    className={cn("h-full rounded-full transition-[width] duration-300 ease-out", tone.bar)}
                    style={{ width: `${percent ?? 0}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between md:block md:text-right">
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Remaining</span>
                <p className={cn("font-mono text-sm font-semibold", tone.text)}>
                  {formatPercentNullable(percent)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function UsageDonuts({
  primaryItems,
  secondaryItems,
  primaryTotal,
  secondaryTotal,
  safeLinePrimary,
  safeLineSecondary,
}: UsageDonutsProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <QuotaBoard title="5h Capacity" items={primaryItems} total={primaryTotal} safeLine={safeLinePrimary} />
      <QuotaBoard title="Weekly Capacity" items={secondaryItems} total={secondaryTotal} safeLine={safeLineSecondary} />
    </div>
  );
}
