import { Cpu, Gauge, HardDrive, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLocalModels } from "@/features/local-models/hooks/use-local-models";
import { formatCompactNumber } from "@/utils/formatters";

export function LocalModelsPanel() {
  const { statusQuery, modelsQuery, metricsQuery } = useLocalModels();
  const status = statusQuery.data;
  const models = modelsQuery.data?.models ?? [];
  const metrics = metricsQuery.data;

  return (
    <section className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-[13px] font-medium uppercase tracking-wider text-muted-foreground">Local Models</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Ollama bridge status and local quota offload.
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          {status?.bridgeRunning ? "Bridge online" : "Bridge offline"}
        </Badge>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-md border px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Cpu className="h-3.5 w-3.5 text-sky-500" />
            Ollama
          </div>
          <p className="mt-1 text-sm font-semibold">{status?.ollamaRunning ? "Running" : "Stopped"}</p>
        </div>
        <div className="rounded-md border px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <HardDrive className="h-3.5 w-3.5 text-emerald-500" />
            Loaded
          </div>
          <p className="mt-1 text-sm font-semibold">{formatCompactNumber(status?.loadedCount ?? 0)}</p>
        </div>
        <div className="rounded-md border px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Gauge className="h-3.5 w-3.5 text-amber-500" />
            Local t/s
          </div>
          <p className="mt-1 text-sm font-semibold">{(metrics?.localTps ?? 0).toFixed(2)}</p>
        </div>
        <div className="rounded-md border px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-violet-500" />
            Quota Saved
          </div>
          <p className="mt-1 text-sm font-semibold">{formatCompactNumber(metrics?.quotaSavedTokens ?? 0)}</p>
        </div>
      </div>

      {models.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Installed models:{" "}
          <span className="font-mono">
            {models.map((model) => model.name).join(", ")}
          </span>
        </p>
      ) : null}
    </section>
  );
}
