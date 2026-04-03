import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw, TerminalSquare } from "lucide-react";

import { AlertMessage } from "@/components/alert-message";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getOmxDashboard, getOmxOverview, runOmxCommand } from "@/features/omx/api";
import type { OmxAction, OmxReasoningLevel } from "@/features/omx/schemas";
import { formatNumber, formatTimeLong } from "@/utils/formatters";

const REASONING_LEVELS: OmxReasoningLevel[] = ["low", "medium", "high", "xhigh"];

type CommandButton = {
  action: OmxAction;
  label: string;
};

const COMMAND_BUTTONS: CommandButton[] = [
  { action: "status", label: "Status" },
  { action: "version", label: "Version" },
  { action: "doctor", label: "Doctor" },
  { action: "doctor_team", label: "Doctor (Team)" },
  { action: "cleanup_dry_run", label: "Cleanup Dry Run" },
  { action: "cleanup", label: "Cleanup" },
  { action: "cancel", label: "Cancel Active Modes" },
  { action: "reasoning_get", label: "Get Reasoning" },
];

function formatTimestamp(value: string | null | undefined): string {
  const { date, time } = formatTimeLong(value);
  if (date === "--" || time === "--") {
    return "--";
  }
  return `${date} ${time}`;
}

function formatToken(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return formatNumber(value);
}

export function OmxPage() {
  const [reasoningLevel, setReasoningLevel] = useState<OmxReasoningLevel>("high");

  const overviewQuery = useQuery({
    queryKey: ["omx", "overview"],
    queryFn: getOmxOverview,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const dashboardQuery = useQuery({
    queryKey: ["omx", "dashboard"],
    queryFn: getOmxDashboard,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  const runMutation = useMutation({
    mutationFn: async ({ action, level }: { action: OmxAction; level?: OmxReasoningLevel }) =>
      runOmxCommand(action, level),
    onSuccess: () => {
      void overviewQuery.refetch();
      void dashboardQuery.refetch();
    },
  });

  const overview = overviewQuery.data;
  const dashboard = dashboardQuery.data;
  const result = runMutation.data;

  const combinedErrorMessage =
    (overviewQuery.error instanceof Error && overviewQuery.error.message) ||
    (dashboardQuery.error instanceof Error && dashboardQuery.error.message) ||
    (runMutation.error instanceof Error && runMutation.error.message) ||
    null;

  const warnings = Array.from(new Set([...(overview?.warnings ?? []), ...(dashboard?.warnings ?? [])]));

  const isRefreshing = overviewQuery.isFetching || dashboardQuery.isFetching;
  const finishedAt = result?.finishedAt ? formatTimeLong(result.finishedAt) : null;
  const dashboardUpdatedAt = formatTimestamp(dashboard?.updatedAt);

  return (
    <div className="animate-fade-in-up space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">OMX Control</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            View runtime health and run safe OMX operations from the dashboard.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void overviewQuery.refetch();
            void dashboardQuery.refetch();
          }}
          disabled={isRefreshing}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
          title="Refresh OMX data"
        >
          <RefreshCw className={`h-4 w-4${isRefreshing ? " animate-spin" : ""}`} />
        </button>
      </div>

      {combinedErrorMessage ? <AlertMessage variant="error">{combinedErrorMessage}</AlertMessage> : null}

      {overview ? (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Install status</p>
            <p className="mt-1 text-sm font-semibold">{overview.available ? "Available" : "Missing"}</p>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Version</p>
            <p className="mt-1 text-sm font-semibold">{overview.version ?? "--"}</p>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Reasoning</p>
            <p className="mt-1 text-sm font-semibold">{overview.reasoning ?? "--"}</p>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Last checked</p>
            <p className="mt-1 text-sm font-semibold">{formatTimeLong(overview.lastCheckedAt).time}</p>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Sessions</p>
            <p className="mt-1 text-sm font-semibold">{dashboard?.sessions.length ?? 0}</p>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Workers</p>
            <p className="mt-1 text-sm font-semibold">{dashboard?.workers.length ?? 0}</p>
          </div>
        </section>
      ) : null}

      {dashboard ? (
        <section className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick OMX Skills</CardTitle>
              <CardDescription>One-line workflow references and launch commands</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard.quickRefs.map((entry) => (
                <div key={entry.key} className="rounded-md border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{entry.label}</p>
                    <code className="rounded bg-muted px-2 py-1 text-xs">{entry.command}</code>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{entry.description}</p>
                </div>
              ))}
              <p className="text-xs text-muted-foreground">Dashboard updated: {dashboardUpdatedAt}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Live OMX Sessions</CardTitle>
              <CardDescription>Active and recent runtime context from OMX state and logs</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Session</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Context</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Last Activity</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.sessions.length ? (
                    dashboard.sessions.map((session) => (
                      <TableRow key={session.id}>
                        <TableCell className="font-mono text-xs">{session.id}</TableCell>
                        <TableCell>{session.status}</TableCell>
                        <TableCell className="max-w-[28rem] truncate" title={session.contextLine}>
                          {session.contextLine}
                        </TableCell>
                        <TableCell>{formatTimestamp(session.startedAt)}</TableCell>
                        <TableCell>{formatTimestamp(session.lastActivityAt)}</TableCell>
                        <TableCell>{session.source}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No OMX sessions detected.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Current Workers</CardTitle>
              <CardDescription>One-line worker job context from OMX team runtime state</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Team</TableHead>
                    <TableHead>Worker</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Job</TableHead>
                    <TableHead>Last Heartbeat</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.workers.length ? (
                    dashboard.workers.map((worker) => (
                      <TableRow key={`${worker.team}:${worker.workerId}`}>
                        <TableCell>{worker.team}</TableCell>
                        <TableCell className="font-mono text-xs">{worker.workerId}</TableCell>
                        <TableCell>{worker.status}</TableCell>
                        <TableCell className="max-w-[28rem] truncate" title={worker.jobLine}>
                          {worker.jobLine}
                        </TableCell>
                        <TableCell>{formatTimestamp(worker.lastHeartbeatAt)}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground">
                        No active worker snapshots found.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Token Analytics</CardTitle>
              <CardDescription>Per-session exact usage and per-worker best-effort visibility</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Per Session
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Session</TableHead>
                      <TableHead className="text-right">Input</TableHead>
                      <TableHead className="text-right">Output</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead>Accuracy</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard.tokenUsage.sessions.length ? (
                      dashboard.tokenUsage.sessions.map((entry) => (
                        <TableRow key={entry.sessionId}>
                          <TableCell className="font-mono text-xs">{entry.sessionId}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.inputTokens)}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.outputTokens)}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.totalTokens)}</TableCell>
                          <TableCell>{entry.exact ? "Exact" : "Best effort"}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-muted-foreground">
                          No session token data available.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Per Worker
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Team</TableHead>
                      <TableHead>Worker</TableHead>
                      <TableHead className="text-right">Input</TableHead>
                      <TableHead className="text-right">Output</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead>Accuracy</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard.tokenUsage.workers.length ? (
                      dashboard.tokenUsage.workers.map((entry) => (
                        <TableRow key={`${entry.team}:${entry.workerId}`}>
                          <TableCell>{entry.team}</TableCell>
                          <TableCell className="font-mono text-xs">{entry.workerId}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.inputTokens)}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.outputTokens)}</TableCell>
                          <TableCell className="text-right">{formatToken(entry.totalTokens)}</TableCell>
                          <TableCell>{entry.exact ? "Exact" : "Best effort"}</TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground">
                          No worker token snapshots available.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              {dashboard.tokenUsage.notes.length ? (
                <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                  {dashboard.tokenUsage.notes.map((note) => (
                    <p key={note}>{note}</p>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </section>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Commands</CardTitle>
            <CardDescription>Allowlisted OMX commands only</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              {COMMAND_BUTTONS.map((command) => (
                <Button
                  key={command.action}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => runMutation.mutate({ action: command.action })}
                  disabled={runMutation.isPending}
                  className="justify-start"
                >
                  {command.label}
                </Button>
              ))}
            </div>

            <div className="rounded-md border p-3">
              <p className="text-xs font-medium text-muted-foreground">Set reasoning effort</p>
              <div className="mt-2 flex items-center gap-2">
                <Select
                  value={reasoningLevel}
                  onValueChange={(value) => setReasoningLevel(value as OmxReasoningLevel)}
                >
                  <SelectTrigger size="sm" className="w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REASONING_LEVELS.map((level) => (
                      <SelectItem key={level} value={level}>
                        {level}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => runMutation.mutate({ action: "reasoning_set", level: reasoningLevel })}
                  disabled={runMutation.isPending}
                >
                  Apply
                </Button>
              </div>
            </div>

            {warnings.length ? (
              <div className="space-y-1 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs">
                {warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TerminalSquare className="h-4 w-4" />
              Command Output
            </CardTitle>
            <CardDescription>
              {result ? `${result.action} (exit ${result.exitCode})` : "Run a command to view output"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-md border bg-muted/30 p-3 text-xs">
              <p>
                <span className="text-muted-foreground">Binary:</span> {overview?.binaryPath ?? "--"}
              </p>
              <p className="mt-1">
                <span className="text-muted-foreground">Runtime env:</span> {overview?.runtimeEnvPath ?? "--"}
              </p>
              <p className="mt-1">
                <span className="text-muted-foreground">Runtime dir:</span> {overview?.runtimeDir ?? "--"}
              </p>
            </div>

            <div className="rounded-md border p-3 text-xs">
              <p className="font-medium">Status snapshot</p>
              <p className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">
                {overview?.statusSummary ?? "--"}
              </p>
            </div>

            {result ? (
              <div className="space-y-2 rounded-md border p-3 text-xs">
                <p>
                  <span className="text-muted-foreground">Command:</span> {result.command.join(" ")}
                </p>
                <p>
                  <span className="text-muted-foreground">Completed:</span>{" "}
                  {finishedAt ? `${finishedAt.date} ${finishedAt.time}` : "--"}
                </p>
                {result.timedOut ? (
                  <AlertMessage variant="error">Command timed out before completion.</AlertMessage>
                ) : null}
                <div className="rounded-md bg-muted/50 p-3 font-mono">
                  <p className="text-[11px] font-medium text-muted-foreground">stdout</p>
                  <pre className="mt-1 whitespace-pre-wrap break-words">{result.stdout || "(empty)"}</pre>
                </div>
                <div className="rounded-md bg-muted/50 p-3 font-mono">
                  <p className="text-[11px] font-medium text-muted-foreground">stderr</p>
                  <pre className="mt-1 whitespace-pre-wrap break-words">{result.stderr || "(empty)"}</pre>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
