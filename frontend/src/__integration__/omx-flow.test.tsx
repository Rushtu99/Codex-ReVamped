import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import App from "@/App";
import { resetOmxEndpointCompatibilityCache } from "@/features/omx/api";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

const OVERVIEW_PAYLOAD = {
  available: true,
  binaryPath: "/data/data/com.termux/files/home/.local/bin/omx",
  runtimeEnvPath: "/data/data/com.termux/files/home/.codex-revamped/runtime.env",
  runtimeDir: "/data/data/com.termux/files/home/tmp-codex-lb-setup-compare",
  version: "oh-my-codex v0.11.12",
  reasoning: "high",
  statusSummary: "No active modes.",
  doctorSummary: "Results: 5 passed",
  warnings: [],
  lastCheckedAt: "2026-04-02T12:30:00Z",
};

const DASHBOARD_PAYLOAD = {
  quickRefs: [
    {
      key: "ralplan",
      label: "Consensus Plan",
      command: '$ralplan "describe the change"',
      description: "Build a consensus plan before execution.",
    },
    {
      key: "team",
      label: "Team Mode",
      command: '$team 3 "implement the approved plan"',
      description: "Start a coordinated multi-worker implementation run.",
    },
  ],
  sessions: [
    {
      id: "omx-session-1",
      status: "running",
      contextLine: "cwd /tmp · pid 123",
      startedAt: "2026-04-02T12:25:00Z",
      lastActivityAt: "2026-04-02T12:30:00Z",
      cwd: "/tmp",
      source: "state",
    },
  ],
  workers: [
    {
      team: "demo-team",
      workerId: "worker-1",
      status: "in_progress",
      jobLine: "Implement OMX dashboard tab",
      role: "executor",
      lastHeartbeatAt: "2026-04-02T12:30:00Z",
      sessionId: "worker-session-1",
    },
  ],
  tokenUsage: {
    sessions: [
      {
        sessionId: "omx-session-1",
        inputTokens: 10,
        outputTokens: 12,
        totalTokens: 22,
        exact: true,
      },
    ],
    workers: [
      {
        team: "demo-team",
        workerId: "worker-1",
        inputTokens: null,
        outputTokens: null,
        totalTokens: null,
        exact: false,
      },
    ],
    notes: ["Worker token metrics are unavailable from OMX worker state; values are marked as N/A."],
  },
  warnings: [],
  updatedAt: "2026-04-02T12:30:00Z",
};

function notFoundResponse() {
  return HttpResponse.json(
    {
      error: {
        code: "not_found",
        message: "Not Found",
      },
    },
    { status: 404 },
  );
}

function registerOmxHandlers({
  overviewStatus = 200,
  dashboardStatus = 200,
}: {
  overviewStatus?: 200 | 404;
  dashboardStatus?: 200 | 404;
} = {}) {
  const requestCounts = {
    overview: 0,
    dashboard: 0,
    run: 0,
  };

  server.use(
    http.get("/api/omx/overview", () => {
      requestCounts.overview += 1;
      if (overviewStatus === 404) {
        return notFoundResponse();
      }
      return HttpResponse.json(OVERVIEW_PAYLOAD);
    }),
    http.get("/api/omx/dashboard", () => {
      requestCounts.dashboard += 1;
      if (dashboardStatus === 404) {
        return notFoundResponse();
      }
      return HttpResponse.json(DASHBOARD_PAYLOAD);
    }),
    http.post("/api/omx/run", async ({ request }) => {
      requestCounts.run += 1;
      const payload = (await request.json()) as { action?: string };
      return HttpResponse.json({
        action: payload.action ?? "status",
        command: ["omx", payload.action === "reasoning_set" ? "reasoning" : "status"],
        exitCode: 0,
        stdout: payload.action === "reasoning_set" ? "Updated model_reasoning_effort: medium" : "No active modes.",
        stderr: "",
        startedAt: "2026-04-02T12:30:10Z",
        finishedAt: "2026-04-02T12:30:11Z",
        timedOut: false,
      });
    }),
  );

  return requestCounts;
}

describe("omx flow integration", () => {
  beforeEach(() => {
    resetOmxEndpointCompatibilityCache();
  });

  it("loads the OMX page and executes allowlisted commands", async () => {
    const user = userEvent.setup({ delay: null });

    registerOmxHandlers();

    window.history.pushState({}, "", "/omx");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "OMX Control" })).toBeInTheDocument();
    expect(await screen.findByText("oh-my-codex v0.11.12")).toBeInTheDocument();
    expect(await screen.findByText("Quick OMX Skills")).toBeInTheDocument();
    expect(await screen.findByText('$team 3 "implement the approved plan"')).toBeInTheDocument();
    expect(await screen.findByText("Implement OMX dashboard tab")).toBeInTheDocument();
    expect((await screen.findAllByText("N/A")).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Status" }));
    expect((await screen.findAllByText(/No active modes/i)).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText(/Updated model_reasoning_effort/i)).toBeInTheDocument();
  }, 30_000);

  it("falls back to /api/omx/dashboard when /api/omx/overview is unavailable", async () => {
    const user = userEvent.setup({ delay: null });
    const requestCounts = registerOmxHandlers({ overviewStatus: 404 });

    window.history.pushState({}, "", "/omx");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "OMX Control" })).toBeInTheDocument();
    expect(await screen.findByText("Implement OMX dashboard tab")).toBeInTheDocument();
    expect(
      await screen.findByText("Using dashboard payload because /api/omx/overview is unavailable."),
    ).toBeInTheDocument();

    const missingEndpointCount = requestCounts.overview;
    const compatibleEndpointCount = requestCounts.dashboard;
    await user.click(screen.getByTitle("Refresh OMX data"));

    await waitFor(() => {
      expect(requestCounts.dashboard).toBeGreaterThan(compatibleEndpointCount);
    });
    expect(requestCounts.overview).toBe(missingEndpointCount);
  });

  it("falls back to /api/omx/overview when /api/omx/dashboard is unavailable", async () => {
    const user = userEvent.setup({ delay: null });
    const requestCounts = registerOmxHandlers({ dashboardStatus: 404 });

    window.history.pushState({}, "", "/omx");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "OMX Control" })).toBeInTheDocument();
    expect(await screen.findByText("oh-my-codex v0.11.12")).toBeInTheDocument();
    expect(await screen.findByText("No OMX sessions detected.")).toBeInTheDocument();
    expect(
      await screen.findByText("Using overview payload because /api/omx/dashboard is unavailable."),
    ).toBeInTheDocument();

    const compatibleEndpointCount = requestCounts.overview;
    const missingEndpointCount = requestCounts.dashboard;
    await user.click(screen.getByTitle("Refresh OMX data"));

    await waitFor(() => {
      expect(requestCounts.overview).toBeGreaterThan(compatibleEndpointCount);
    });
    expect(requestCounts.dashboard).toBe(missingEndpointCount);
  });
});
