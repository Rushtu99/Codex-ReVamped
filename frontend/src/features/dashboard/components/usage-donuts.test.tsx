import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UsageDonuts } from "@/features/dashboard/components/usage-donuts";

function item(overrides: {
  accountId: string;
  label: string;
  value: number;
  remainingPercent: number;
  color: string;
}) {
  return { ...overrides, labelSuffix: "", isEmail: true };
}

describe("UsageDonuts", () => {
  it("renders only the 5h capacity board", () => {
    render(
      <UsageDonuts
        primaryItems={[
          item({
            accountId: "acc-1",
            label: "primary@example.com",
            value: 120,
            remainingPercent: 60,
            color: "#7bb661",
          }),
        ]}
        primaryTotal={200}
      />,
    );

    expect(screen.getByText("5h Capacity")).toBeInTheDocument();
    expect(screen.queryByText("Weekly Capacity")).not.toBeInTheDocument();
    expect(screen.getByText("primary@example.com")).toBeInTheDocument();
  });

  it("renders safe line marker when primary depletion exists", () => {
    render(
      <UsageDonuts
        primaryItems={[
          item({
            accountId: "acc-1",
            label: "primary@example.com",
            value: 120,
            remainingPercent: 60,
            color: "#7bb661",
          }),
        ]}
        primaryTotal={200}
        safeLinePrimary={{ safePercent: 60, riskLevel: "warning" }}
      />,
    );

    expect(screen.getByText("Watch depletion")).toBeInTheDocument();
  });
});

