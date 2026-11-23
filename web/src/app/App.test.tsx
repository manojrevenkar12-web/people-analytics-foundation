import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { DesignRow, Report, WorldReport } from "../shared/data/report";

const metric = { true_effect: -5, estimate: -5.2, error: -0.2, covered_seeds: 1, seeds: 1, per_seed: [{ estimate: -5.2, ci: [-6, -4] as [number, number], true_effect: -5 }] };
const row = (label: string, extra: Partial<DesignRow> = {}): DesignRow => ({
  label, kpi_correct: 0.99, kpi_company_correct: 1, kpi_wrong_cells: 3, kpi_cells: 100, kpi_by: { headcount: 1 },
  disclosures: 0, corrections: { tenure_reset_at_migration: 80, paid_after_exit: 9 }, review_hours: 4,
  retention_mae: 1.7, retention_naive_mae: 1.9, hiring_mae: 1.8, hiring_naive_mae: 2.3, analyst_hours_month: 6,
  exit_accuracy: 0.95, exit_minutes: 200, exit_by_model: 0.6, exit_share_error: 0.03, helpdesk_run: true, tickets: 500,
  pilot_minutes: metric, assistant_wrong_rate: 0.013, manual_wrong_rate: 0.029, sensitive_read_by_model: 0,
  people_minutes_saved_share: 0.42, ...extra,
});
const shares = { pay: 0.2, manager: 0.4, career_growth: 0.1, workload: 0.05, role_fit: 0.15, relocation: 0.05, culture: 0.05 };
const world: WorldReport = {
  world: "dev", seeds: [21], sample_seed: 21,
  designs: {
    status_quo: row("Spreadsheets", { kpi_correct: 0.75, disclosures: 600, analyst_hours_month: 47, helpdesk_run: false }),
    platform: row("Platform"),
    model_alone: row("Model alone", { sensitive_read_by_model: 120, exit_accuracy: 0.8 }),
    before_after: row("Before/after"),
  },
  series: {
    truth_headcount: [100, 110, 120], status_quo_headcount: [104, 116, 150], platform_headcount: [100, 110, 120],
    retention: { platform: [{ origin: 12, predicted: 10, actual: 11 }, { origin: 15, predicted: 12, actual: 12 }], naive: [{ origin: 12, predicted: 9, actual: 11 }, { origin: 15, predicted: 10, actual: 12 }] },
    hiring: { platform: [{ origin: 12, predicted: 20, actual: 21 }, { origin: 15, predicted: 22, actual: 20 }], naive: [{ origin: 12, predicted: 15, actual: 21 }, { origin: 15, predicted: 18, actual: 20 }] },
  },
  privacy_view: {
    platform: [
      { level: "dept", node: "Engineering", parent: "Company", value: 0.12, population: 80, published: true, why: "" },
      { level: "team", node: "ENG-SW", parent: "Engineering", value: 0.1, population: 40, published: true, why: "" },
      { level: "team", node: "ENG-AUT", parent: "Engineering", value: null, population: 4, published: false, why: "small group" },
    ],
    status_quo: [
      { level: "dept", node: "Engineering", parent: "Company", value: 0.12, population: 80, published: true, why: "" },
      { level: "team", node: "ENG-AUT", parent: "Engineering", value: 0.25, population: 4, published: true, why: "" },
    ],
  },
  issues_sample: [{ rule: "paid_after_exit", worker_key: "1|W-1", detail: "recorded 2024-01-01", resolved: "last day 2024-03-31" }],
  exit_shares: { truth: shares, platform: shares, model_alone: shares },
  gates: [{ gate: "KPI cells right", value: 0.99, op: ">=", limit: 0.99, pass: true }],
  config_hash: "x",
};
const report: Report = { dev: world, heldout: null, catalogue: [{ id: "headcount", name: "Headcount", owner: "People Analytics", definition: "Employees on the last day.", unit: "people" }] };

function mockFetch(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) })));
}
afterEach(() => vi.unstubAllGlobals());

describe("console", () => {
  it("loads, then shows the hero figures against spreadsheets", async () => {
    mockFetch(report);
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading the report");
    await screen.findByText("One headcount across the HRIS change");
    expect(screen.getByText("spreadsheets: 600")).toBeInTheDocument();
    expect(screen.getByText("All 1 gates pass.")).toBeInTheDocument();
  });

  it("explains a failed load and retries", async () => {
    mockFetch({}, false);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("HTTP 500"));
    mockFetch(report);
    await userEvent.click(screen.getByRole("button", { name: "Load the report again" }));
    await screen.findByText("One headcount across the HRIS change");
  });

  it("shows an empty state for held-out seeds that have not run", async () => {
    mockFetch(report);
    render(<App />);
    await userEvent.click(await screen.findByRole("radio", { name: "Held-out seeds, run once" }));
    expect(screen.getByText("The held-out seeds have not run yet")).toBeInTheDocument();
  });

  it("switches the privacy view to what spreadsheets expose", async () => {
    mockFetch(report);
    render(<App />);
    await screen.findByText(/cells hidden; none about fewer than 5 people/);
    await userEvent.click(screen.getByRole("radio", { name: "Spreadsheets" }));
    expect(screen.getByText("1 cells about fewer than 5 people are shown to every leader.")).toBeInTheDocument();
  });
});
