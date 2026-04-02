import { SparklineChart } from "@/components/sparkline-chart";
import type { DashboardStat } from "@/features/dashboard/utils";
import { cn } from "@/lib/utils";

const ACCENT_STYLES = [
  "bg-primary/12 text-primary",
  "bg-amber-500/12 text-amber-600 dark:text-amber-400",
  "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400",
  "bg-red-500/10 text-red-600 dark:bg-red-500/15 dark:text-red-400",
];

export type StatsGridProps = {
  stats: DashboardStat[];
};

export function StatsGrid({ stats }: StatsGridProps) {
  return (
    <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
      {stats.map((stat, index) => {
        const Icon = stat.icon;
        const accent = ACCENT_STYLES[index % ACCENT_STYLES.length];
        return (
          <div
            key={stat.label}
            className="animate-fade-in-up rounded-md border bg-card px-4 py-3"
            style={{ animationDelay: `${index * 75}ms` }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{stat.label}</span>
              <div className={cn("flex h-7 w-7 items-center justify-center rounded-md", accent)}>
                <Icon className="h-4 w-4" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-2">
              <p className="text-[1.35rem] font-semibold tracking-[-0.02em]">{stat.value}</p>
              {stat.meta ? (
                <p className="mt-1 text-xs text-muted-foreground">{stat.meta}</p>
              ) : null}
            </div>
            {stat.trend.length > 0 ? (
              <div className="mt-2">
                <SparklineChart data={stat.trend} color={stat.trendColor} index={index} />
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
