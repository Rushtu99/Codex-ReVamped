import { Cpu, Gauge, HardDrive, ShieldCheck, ShieldX } from "lucide-react";

import { AlertMessage } from "@/components/alert-message";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useLocalModels } from "@/features/local-models/hooks/use-local-models";
import { formatCompactNumber, formatTimeLong } from "@/utils/formatters";

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "--";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function LocalModelsPage() {
  const { statusQuery, modelsQuery, metricsQuery } = useLocalModels();

  const status = statusQuery.data;
  const models = modelsQuery.data?.models ?? [];
  const metrics = metricsQuery.data;
  const errorMessage =
    (statusQuery.error instanceof Error && statusQuery.error.message) ||
    (modelsQuery.error instanceof Error && modelsQuery.error.message) ||
    (metricsQuery.error instanceof Error && metricsQuery.error.message) ||
    null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Local Models</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Live Ollama status and model inventory from the local bridge.
        </p>
      </div>

      {errorMessage ? <AlertMessage variant="error">{errorMessage}</AlertMessage> : null}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-md border bg-card px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Cpu className="h-3.5 w-3.5 text-sky-500" />
            Ollama
          </div>
          <p className="mt-2 text-xl font-semibold">
            {status?.ollamaRunning ? "Running" : "Stopped"}
          </p>
        </div>
        <div className="rounded-md border bg-card px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <HardDrive className="h-3.5 w-3.5 text-emerald-500" />
            Loaded
          </div>
          <p className="mt-2 text-xl font-semibold">{formatCompactNumber(status?.loadedCount ?? 0)}</p>
        </div>
        <div className="rounded-md border bg-card px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <Gauge className="h-3.5 w-3.5 text-amber-500" />
            Local t/s
          </div>
          <p className="mt-2 text-xl font-semibold">{(metrics?.localTps ?? 0).toFixed(2)}</p>
        </div>
        <div className="rounded-md border bg-card px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-violet-500" />
            Quota Saved
          </div>
          <p className="mt-2 text-xl font-semibold">{formatCompactNumber(metrics?.quotaSavedTokens ?? 0)}</p>
        </div>
      </section>

      <section className="rounded-md border bg-card">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-sm font-medium">Installed Models</h2>
          <Badge variant="outline" className="text-xs">
            Bridge {status?.bridgeRunning ? "online" : "offline"}
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <Table className="min-w-[880px]">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead>Loaded</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="text-right">VRAM</TableHead>
                <TableHead>Last used</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                    No local model metadata available.
                  </TableCell>
                </TableRow>
              ) : (
                models.map((model) => {
                  const lastUsed = formatTimeLong(model.lastUsedAt);
                  return (
                    <TableRow key={model.name}>
                      <TableCell className="font-mono text-xs">{model.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={model.loaded ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>
                          {model.loaded ? <ShieldCheck className="mr-1 h-3 w-3" /> : <ShieldX className="mr-1 h-3 w-3" />}
                          {model.loaded ? "Loaded" : "Idle"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">{formatBytes(model.sizeBytes)}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{formatBytes(model.loadedSizeBytes)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {model.lastUsedAt ? `${lastUsed.time} ${lastUsed.date}` : "--"}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
