import { z } from "zod";

import { ApiError, get, post } from "@/lib/api-client";
import {
  OmxDashboardSchema,
  OmxOverviewSchema,
  OmxRunCommandResultSchema,
  type OmxAction,
  type OmxDashboard,
  type OmxOverview,
  type OmxReasoningLevel,
} from "@/features/omx/schemas";

const OMX_API_PATH = "/api/omx";
type OmxEndpoint = "overview" | "dashboard";
type OmxEndpointAvailability = "unknown" | "available" | "missing";

const omxEndpointAvailability: Record<OmxEndpoint, OmxEndpointAvailability> = {
  overview: "unknown",
  dashboard: "unknown",
};

export function resetOmxEndpointCompatibilityCache() {
  omxEndpointAvailability.overview = "unknown";
  omxEndpointAvailability.dashboard = "unknown";
}

function toOverviewFromDashboard(dashboard: OmxDashboard): OmxOverview {
  return {
    available: true,
    binaryPath: null,
    runtimeEnvPath: null,
    runtimeDir: null,
    version: null,
    reasoning: null,
    statusSummary: dashboard.warnings[0] ?? "OMX dashboard data available.",
    doctorSummary: null,
    warnings: [
      ...dashboard.warnings,
      "Using dashboard payload because /api/omx/overview is unavailable.",
    ],
    lastCheckedAt: dashboard.updatedAt,
  };
}

function toDashboardFromOverview(overview: OmxOverview): OmxDashboard {
  return {
    quickRefs: [],
    sessions: [],
    workers: [],
    tokenUsage: {
      sessions: [],
      workers: [],
      notes: overview.statusSummary ? [overview.statusSummary] : [],
    },
    warnings: [
      ...overview.warnings,
      "Using overview payload because /api/omx/dashboard is unavailable.",
    ],
    updatedAt: overview.lastCheckedAt,
  };
}

function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 404 || error.status === 405);
}

function markOmxEndpointAvailability(endpoint: OmxEndpoint, availability: OmxEndpointAvailability) {
  omxEndpointAvailability[endpoint] = availability;
}

function parseOverviewPayload(payload: unknown): OmxOverview | null {
  const overview = OmxOverviewSchema.safeParse(payload);
  if (overview.success) {
    return overview.data;
  }

  const dashboard = OmxDashboardSchema.safeParse(payload);
  if (dashboard.success) {
    return toOverviewFromDashboard(dashboard.data);
  }

  return null;
}

function parseDashboardPayload(payload: unknown): OmxDashboard | null {
  const dashboard = OmxDashboardSchema.safeParse(payload);
  if (dashboard.success) {
    return dashboard.data;
  }

  const overview = OmxOverviewSchema.safeParse(payload);
  if (overview.success) {
    return toDashboardFromOverview(overview.data);
  }

  return null;
}

function getOmxEndpointCandidates(primary: OmxEndpoint, fallback: OmxEndpoint): OmxEndpoint[] {
  const ordered = [primary, fallback].filter((endpoint, index, endpoints) => endpoints.indexOf(endpoint) === index);
  const available = ordered.filter((endpoint) => omxEndpointAvailability[endpoint] !== "missing");
  const missing = ordered.filter((endpoint) => omxEndpointAvailability[endpoint] === "missing");

  return [...available, ...missing];
}

async function getOmxCompatiblePayload<T>({
  primaryEndpoint,
  fallbackEndpoint,
  parsePayload,
}: {
  primaryEndpoint: OmxEndpoint;
  fallbackEndpoint: OmxEndpoint;
  parsePayload: (payload: unknown) => T | null;
}): Promise<T> {
  const endpoints = getOmxEndpointCandidates(primaryEndpoint, fallbackEndpoint);
  let missingEndpointError: unknown = null;

  for (const endpoint of endpoints) {
    try {
      const payload = await get(`${OMX_API_PATH}/${endpoint}`, z.unknown());
      markOmxEndpointAvailability(endpoint, "available");

      const parsed = parsePayload(payload);
      if (parsed) {
        return parsed;
      }

      throw new Error(`Received unsupported payload from ${OMX_API_PATH}/${endpoint}.`);
    } catch (error) {
      if (!isNotFound(error)) {
        throw error;
      }

      markOmxEndpointAvailability(endpoint, "missing");
      missingEndpointError = error;
    }
  }

  if (missingEndpointError) {
    throw missingEndpointError;
  }

  throw new Error("No compatible OMX endpoint is available.");
}

export async function getOmxOverview() {
  return getOmxCompatiblePayload({
    primaryEndpoint: "overview",
    fallbackEndpoint: "dashboard",
    parsePayload: parseOverviewPayload,
  });
}

export async function getOmxDashboard() {
  return getOmxCompatiblePayload({
    primaryEndpoint: "dashboard",
    fallbackEndpoint: "overview",
    parsePayload: parseDashboardPayload,
  });
}

export function runOmxCommand(action: OmxAction, level?: OmxReasoningLevel) {
  return post(`${OMX_API_PATH}/run`, OmxRunCommandResultSchema, {
    body: {
      action,
      ...(level ? { level } : {}),
    },
  });
}
