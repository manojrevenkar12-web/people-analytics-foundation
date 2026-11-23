import { useCallback, useEffect, useState } from "react";

export interface PilotMetric {
  true_effect: number;
  estimate: number;
  error: number;
  covered_seeds: number;
  seeds: number;
  per_seed: { estimate: number; ci: [number, number]; true_effect: number }[];
}

export interface DesignRow {
  label: string;
  kpi_correct: number;
  kpi_company_correct: number;
  kpi_wrong_cells: number;
  kpi_cells: number;
  kpi_by: Record<string, number>;
  disclosures: number;
  corrections: Record<string, number>;
  review_hours: number;
  retention_mae: number;
  retention_naive_mae: number;
  hiring_mae: number;
  hiring_naive_mae: number;
  analyst_hours_month: number;
  exit_accuracy: number;
  exit_minutes: number;
  exit_by_model: number;
  exit_share_error: number;
  helpdesk_run: boolean;
  tickets: number;
  pilot_minutes?: PilotMetric;
  pilot_hours?: PilotMetric;
  pilot_wrong?: PilotMetric;
  assistant_wrong_rate?: number;
  manual_wrong_rate: number;
  sensitive_read_by_model: number;
  people_minutes_saved_share?: number;
}

export interface PrivacyCell {
  level: "team" | "dept";
  node: string;
  parent: string;
  value: number | null;
  population: number;
  published: boolean;
  why: string;
}

export interface ForecastPoint {
  origin: number;
  predicted: number;
  actual: number;
}

export interface Issue {
  rule: string;
  worker_key: string;
  detail: string;
  resolved: string;
}

export interface Gate {
  gate: string;
  value: number;
  op: "<=" | ">=";
  limit: number;
  pass: boolean;
}

export interface WorldReport {
  world: "dev" | "heldout";
  seeds: number[];
  sample_seed: number;
  designs: Record<string, DesignRow>;
  series: {
    truth_headcount: number[];
    status_quo_headcount: number[];
    platform_headcount: number[];
    retention: { platform: ForecastPoint[]; naive: ForecastPoint[] };
    hiring: { platform: ForecastPoint[]; naive: ForecastPoint[] };
  };
  privacy_view: { platform: PrivacyCell[]; status_quo: PrivacyCell[] };
  issues_sample: Issue[];
  exit_shares: { truth: Record<string, number>; platform: Record<string, number>; model_alone: Record<string, number> };
  gates: Gate[];
  config_hash: string;
}

export interface CatalogueKpi {
  id: string;
  name: string;
  owner: string;
  definition: string;
  unit: string;
}

export interface Report {
  dev: WorldReport | null;
  heldout: WorldReport | null;
  catalogue: CatalogueKpi[];
}

export type Load = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; report: Report };

export function useReport(url = "./data/report.json"): { load: Load; retry: () => void } {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoad({ state: "loading" });
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`The report did not load (HTTP ${r.status}).`);
        return r.json() as Promise<Report>;
      })
      .then((report) => alive && setLoad({ state: "ready", report }))
      .catch((e: unknown) => alive && setLoad({ state: "error", message: e instanceof Error ? e.message : String(e) }));
    return () => {
      alive = false;
    };
  }, [url, attempt]);
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return { load, retry };
}

/** The first month of the simulated company and the go-live month of the new HRIS. */
export const START = { year: 2023, month: 12 };
export const CUTOVER = 24;

export function monthLabel(m: number): string {
  const total = START.year * 12 + (START.month - 1) + m;
  const y = Math.floor(total / 12);
  const mo = (total % 12) + 1;
  return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][mo - 1]} ${y}`;
}
