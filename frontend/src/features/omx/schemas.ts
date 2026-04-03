import { z } from "zod";

export const OmxReasoningLevelSchema = z.enum(["low", "medium", "high", "xhigh"]);

export const OmxOverviewSchema = z.object({
  available: z.boolean(),
  binaryPath: z.string().nullable(),
  runtimeEnvPath: z.string().nullable(),
  runtimeDir: z.string().nullable(),
  version: z.string().nullable(),
  reasoning: OmxReasoningLevelSchema.nullable(),
  statusSummary: z.string().nullable(),
  doctorSummary: z.string().nullable(),
  warnings: z.array(z.string()),
  lastCheckedAt: z.string().datetime({ offset: true }),
});

export const OmxQuickRefSchema = z.object({
  key: z.string(),
  label: z.string(),
  command: z.string(),
  description: z.string(),
});

export const OmxDashboardSessionSchema = z.object({
  id: z.string(),
  status: z.string(),
  contextLine: z.string(),
  startedAt: z.string().datetime({ offset: true }).nullable().optional().default(null),
  lastActivityAt: z.string().datetime({ offset: true }).nullable().optional().default(null),
  cwd: z.string().nullable().optional().default(null),
  source: z.string(),
});

export const OmxDashboardWorkerSchema = z.object({
  team: z.string(),
  workerId: z.string(),
  status: z.string(),
  jobLine: z.string(),
  role: z.string().nullable().optional().default(null),
  lastHeartbeatAt: z.string().datetime({ offset: true }).nullable().optional().default(null),
  sessionId: z.string().nullable().optional().default(null),
});

export const OmxSessionTokenUsageSchema = z.object({
  sessionId: z.string(),
  inputTokens: z.number().int().nullable().optional().default(null),
  outputTokens: z.number().int().nullable().optional().default(null),
  totalTokens: z.number().int().nullable().optional().default(null),
  exact: z.boolean(),
});

export const OmxWorkerTokenUsageSchema = z.object({
  team: z.string(),
  workerId: z.string(),
  inputTokens: z.number().int().nullable().optional().default(null),
  outputTokens: z.number().int().nullable().optional().default(null),
  totalTokens: z.number().int().nullable().optional().default(null),
  exact: z.boolean(),
});

export const OmxTokenUsageSchema = z.object({
  sessions: z.array(OmxSessionTokenUsageSchema),
  workers: z.array(OmxWorkerTokenUsageSchema),
  notes: z.array(z.string()),
});

export const OmxDashboardSchema = z.object({
  quickRefs: z.array(OmxQuickRefSchema),
  sessions: z.array(OmxDashboardSessionSchema),
  workers: z.array(OmxDashboardWorkerSchema),
  tokenUsage: OmxTokenUsageSchema,
  warnings: z.array(z.string()),
  updatedAt: z.string().datetime({ offset: true }),
});

export const OmxActionSchema = z.enum([
  "version",
  "status",
  "doctor",
  "doctor_team",
  "cleanup",
  "cleanup_dry_run",
  "cancel",
  "reasoning_get",
  "reasoning_set",
]);

export const OmxRunCommandRequestSchema = z.object({
  action: OmxActionSchema,
  level: OmxReasoningLevelSchema.optional(),
});

export const OmxRunCommandResultSchema = z.object({
  action: OmxActionSchema,
  command: z.array(z.string()),
  exitCode: z.number().int(),
  stdout: z.string(),
  stderr: z.string(),
  startedAt: z.string().datetime({ offset: true }),
  finishedAt: z.string().datetime({ offset: true }),
  timedOut: z.boolean(),
});

export type OmxOverview = z.infer<typeof OmxOverviewSchema>;
export type OmxDashboard = z.infer<typeof OmxDashboardSchema>;
export type OmxAction = z.infer<typeof OmxActionSchema>;
export type OmxReasoningLevel = z.infer<typeof OmxReasoningLevelSchema>;
export type OmxRunCommandRequest = z.infer<typeof OmxRunCommandRequestSchema>;
export type OmxRunCommandResult = z.infer<typeof OmxRunCommandResultSchema>;
