import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import App from "@/App";
import {
  createDashboardOverview,
  createDefaultRequestLogs,
  createRequestLogFilterOptions,
  createRequestLogsResponse,
} from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

describe("dashboard flow integration", () => {
  it("loads dashboard, keeps weekly panel hidden, and preserves request log filters", async () => {
    const user = userEvent.setup({ delay: null });
    const logs = createDefaultRequestLogs();

    let overviewCalls = 0;
    let requestLogCalls = 0;

    server.use(
      http.get("/api/dashboard/overview", () => {
        overviewCalls += 1;
        return HttpResponse.json(createDashboardOverview());
      }),
      http.get("/api/request-logs", ({ request }) => {
        requestLogCalls += 1;
        const url = new URL(request.url);
        const limit = Number(url.searchParams.get("limit") ?? "25");
        const offset = Number(url.searchParams.get("offset") ?? "0");
        const page = logs.slice(offset, Math.min(logs.length, offset + limit));
        return HttpResponse.json(createRequestLogsResponse(page, 100, true));
      }),
      http.get("/api/request-logs/options", () => HttpResponse.json(createRequestLogFilterOptions())),
      http.get("/api/local-models/status", () =>
        HttpResponse.json({
          bridgeRunning: false,
          ollamaRunning: false,
          endpoint: null,
          loadedCount: 0,
        }),
      ),
      http.get("/api/local-models/models", () =>
        HttpResponse.json({
          models: [],
        }),
      ),
      http.get("/api/local-models/metrics", () =>
        HttpResponse.json({
          localTps: 0,
          requestCount: 0,
          queueDepth: 0,
          quotaSavedTokens: 0,
          quotaSavedPercent: 0,
        }),
      ),
    );

    window.history.pushState({}, "", "/dashboard");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "CodexLB ReVamped" })).toBeInTheDocument();
    expect(await screen.findByText("Request traffic")).toBeInTheDocument();
    expect(await screen.findByTestId("account-health-summary")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect((await screen.findAllByText("5m")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("15m")).length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(overviewCalls).toBeGreaterThan(0);
      expect(requestLogCalls).toBeGreaterThan(0);
    });

    expect(screen.queryByText("5h Capacity")).not.toBeInTheDocument();
    expect(screen.queryByText("Weekly Capacity")).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Search request id, account, model, error..."), "quota");
    await waitFor(() => {
      expect(requestLogCalls).toBeGreaterThan(1);
    });

    expect(await screen.findByDisplayValue("quota")).toBeInTheDocument();
  }, 30_000);
});
