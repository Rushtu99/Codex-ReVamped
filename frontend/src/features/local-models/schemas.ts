import { z } from "zod";

export const LocalModelStatusSchema = z.object({
  bridgeRunning: z.boolean(),
  ollamaRunning: z.boolean(),
  endpoint: z.string().nullable().optional().default(null),
  loadedCount: z.number().int().nonnegative(),
});

export const LocalModelSchema = z.object({
  name: z.string(),
  digest: z.string().nullable().optional().default(null),
  sizeBytes: z.number().int().nonnegative(),
  modifiedAt: z.string().datetime({ offset: true }).nullable().optional().default(null),
  loaded: z.boolean(),
  loadedSizeBytes: z.number().int().nonnegative(),
  lastUsedAt: z.string().datetime({ offset: true }).nullable().optional().default(null),
});

export const LocalModelListSchema = z.object({
  models: z.array(LocalModelSchema),
});

export const LocalModelMetricsSchema = z.object({
  localTps: z.number(),
  requestCount: z.number().int().nonnegative(),
  queueDepth: z.number().int().nonnegative(),
  quotaSavedTokens: z.number().int().nonnegative(),
  quotaSavedPercent: z.number(),
});

export type LocalModelStatus = z.infer<typeof LocalModelStatusSchema>;
export type LocalModel = z.infer<typeof LocalModelSchema>;
export type LocalModelList = z.infer<typeof LocalModelListSchema>;
export type LocalModelMetrics = z.infer<typeof LocalModelMetricsSchema>;
