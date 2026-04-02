import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { STATUS_LABELS } from "@/utils/constants";

type StatusValue = "active" | "paused" | "limited" | "exceeded" | "deactivated";

const statusClassMap: Record<StatusValue, string> = {
  active: "border-emerald-500/20 bg-emerald-500/12 text-emerald-700 dark:text-emerald-400",
  paused: "border-amber-500/20 bg-amber-500/12 text-amber-700 dark:text-amber-400",
  limited: "border-orange-500/20 bg-orange-500/12 text-orange-700 dark:text-orange-400",
  exceeded: "border-red-500/20 bg-red-500/12 text-red-700 dark:text-red-400",
  deactivated: "border-zinc-500/20 bg-zinc-500/12 text-zinc-700 dark:text-zinc-400",
};

export type StatusBadgeProps = {
  status: StatusValue;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const className = statusClassMap[status] ?? statusClassMap.deactivated;
  const label = STATUS_LABELS[status] ?? status;

  return (
    <Badge className={cn("gap-1.5 rounded-md px-2 py-0.5", className)} variant="outline">
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label}
    </Badge>
  );
}
