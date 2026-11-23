"""The study: every design on the development seeds, or once on the held-out seeds behind a lock."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from paf.lab import simulate
from paf.lab.tidy import tidy

ROOT = simulate.ROOT
CONFIG = simulate.CONFIG
REPORTS = ROOT / "reports"
LOCK = REPORTS / "heldout.lock"


def config_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(CONFIG.glob("*.yml")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _job(args: tuple[str, int, str]) -> dict:
    world_name, seed, name = args
    return simulate.run(world_name, seed, name, simulate.designs()[name])


def run_world(world_name: str, seeds: list[int], workers: int = 2) -> dict[str, list[dict]]:
    names = list(simulate.designs())
    jobs = [(world_name, s, n) for s in seeds for n in names]
    # one world per process: group by seed so each worker builds a seed's world once
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_job, jobs, chunksize=len(names)))
    out: dict[str, list[dict]] = {n: [] for n in names}
    for (_, _, n), r in zip(jobs, results, strict=True):
        out[n].append(r)
    return out


def _mean(xs: list[float]) -> float:
    return float(np.mean(xs))


def summarize(world_name: str, seeds: list[int], runs: dict[str, list[dict]]) -> dict:
    rows: dict[str, dict[str, Any]] = {}
    for name, rs in runs.items():
        hd = [r["helpdesk"] for r in rs]
        row: dict[str, Any] = {
            "label": rs[0]["label"],
            "kpi_correct": _mean([r["kpi"]["correct_share"] for r in rs]),
            "kpi_company_correct": _mean([r["kpi"]["company_correct_share"] for r in rs]),
            "kpi_wrong_cells": int(sum(r["kpi"]["wrong_cells"] for r in rs)),
            "kpi_cells": int(sum(r["kpi"]["cells"] for r in rs)),
            "kpi_by": {k: _mean([r["kpi"]["by_kpi"].get(k, np.nan) for r in rs]) for k in rs[0]["kpi"]["by_kpi"]},
            "disclosures": int(sum(r["disclosures"]["total"] for r in rs)),
            "corrections": {
                k: int(sum(r["corrections"].get(k, 0) for r in rs))
                for k in sorted({k for r in rs for k in r["corrections"]})
            },
            "review_hours": _mean([r["review_minutes"] for r in rs]) / 60,
            "retention_mae": _mean([r["retention_mae"] for r in rs]),
            "retention_naive_mae": _mean([r["retention_naive_mae"] for r in rs]),
            "hiring_mae": _mean([r["hiring_mae"] for r in rs]),
            "hiring_naive_mae": _mean([r["hiring_naive_mae"] for r in rs]),
            "analyst_hours_month": _mean([r["analyst_hours_month"] for r in rs]),
            "exit_accuracy": _mean([r["exit_coding"]["accuracy"] for r in rs]),
            "exit_minutes": _mean([r["exit_coding"]["people_minutes"] for r in rs]),
            "exit_by_model": _mean([r["exit_coding"]["by_model_share"] for r in rs]),
            "exit_share_error": _mean([r["exit_coding"]["share_error"] for r in rs]),
            "helpdesk_run": bool(hd[0]["run"]),
            "tickets": int(sum(h["tickets"] for h in hd)),
        }
        if hd[0]["run"]:
            for metric in ("minutes", "hours", "wrong"):
                row[f"pilot_{metric}"] = {
                    "true_effect": _mean([h[metric]["true_effect"] for h in hd]),
                    "estimate": _mean([h[metric]["estimate"] for h in hd]),
                    "error": _mean([h[metric]["error"] for h in hd]),
                    "covered_seeds": int(sum(h[metric]["covered"] for h in hd)),
                    "seeds": len(hd),
                    "per_seed": [
                        {
                            "estimate": h[metric]["estimate"],
                            "ci": h[metric]["ci"],
                            "true_effect": h[metric]["true_effect"],
                        }
                        for h in hd
                    ],
                }
            row["assistant_wrong_rate"] = _mean([h["treated_wrong_rate"] for h in hd])
            row["manual_wrong_rate"] = _mean([h["control_wrong_rate"] for h in hd])
            row["sensitive_read_by_model"] = int(sum(h["sensitive_read_by_model"] for h in hd))
            row["people_minutes_saved_share"] = 1 - _mean(
                [h["people_minutes_if_rolled_out"] / h["people_minutes_manual"] for h in hd]
            )
        else:
            row["manual_wrong_rate"] = _mean([h["wrong_rate"] for h in hd])
            row["sensitive_read_by_model"] = 0
        rows[name] = row
    first = {n: rs[0] for n, rs in runs.items()}
    return {
        "world": world_name,
        "seeds": seeds,
        "designs": rows,
        "config_hash": config_hash(),
        "sample_seed": seeds[0],
        "series": {
            "truth_headcount": first["platform"]["series"]["truth_headcount"],
            "status_quo_headcount": first["status_quo"]["series"]["headcount"],
            "platform_headcount": first["platform"]["series"]["headcount"],
            "retention": {
                "platform": first["platform"]["series"]["retention"],
                "naive": first["naive_forecast"]["series"]["retention"],
            },
            "hiring": {
                "platform": first["platform"]["series"]["hiring"],
                "naive": first["naive_forecast"]["series"]["hiring"],
            },
        },
        "privacy_view": {
            "platform": first["platform"]["privacy_view"],
            "status_quo": first["status_quo"]["privacy_view"],
        },
        "issues_sample": first["platform"]["issues_sample"],
        "exit_shares": {
            "truth": first["platform"]["exit_coding"]["true_share"],
            "platform": first["platform"]["exit_coding"]["estimated_share"],
            "model_alone": first["model_alone"]["exit_coding"]["estimated_share"],
        },
        "pilot_sample": {n: first[n]["helpdesk"] for n in ("platform", "before_after")},
    }


def judge(summary: dict) -> list[dict]:
    g = simulate.load("gates")
    d = summary["designs"]
    p, sq = d["platform"], d["status_quo"]
    pm = p["pilot_minutes"]
    checks = [
        ("Published KPI cells that match the truth", p["kpi_correct"], ">=", g["kpi_correct_min"]),
        (
            "Cells about fewer than 5 people revealed, directly or by subtraction",
            p["disclosures"],
            "<=",
            g["disclosures_max"],
        ),
        (
            "Retention forecast error / trailing-average error",
            p["retention_mae"] / p["retention_naive_mae"],
            "<=",
            g["retention_ratio_max"],
        ),
        (
            "Hiring forecast error / trailing-average error",
            p["hiring_mae"] / p["hiring_naive_mae"],
            "<=",
            g["hiring_ratio_max"],
        ),
        (
            "Seeds where the pilot's interval covers the true time saved",
            pm["covered_seeds"] / pm["seeds"],
            ">=",
            g["pilot_coverage_min"],
        ),
        ("Sensitive questions read by the model", p["sensitive_read_by_model"], "<=", g["sensitive_read_max"]),
        (
            "Assistant wrong-answer rate minus the People team's",
            p["assistant_wrong_rate"] - p["manual_wrong_rate"],
            "<=",
            g["assistant_extra_wrong_max"],
        ),
        ("Exit comments coded to the real reason", p["exit_accuracy"], ">=", g["exit_accuracy_min"]),
        (
            "Analyst hours a month / spreadsheet hours",
            p["analyst_hours_month"] / sq["analyst_hours_month"],
            "<=",
            g["analyst_hours_ratio_max"],
        ),
    ]
    return [
        {
            "gate": n,
            "value": float(v),
            "op": op,
            "limit": float(lim),
            "pass": bool(v <= lim if op == "<=" else v >= lim),
        }
        for n, v, op, lim in checks
    ]


def write(name: str, summary: dict) -> Path:
    REPORTS.mkdir(exist_ok=True)
    summary["gates"] = judge(summary)
    path = REPORTS / f"{name}.json"
    path.write_text(json.dumps(tidy(summary), indent=1, sort_keys=True, default=float) + "\n")
    return path


def run_dev(workers: int = 2) -> Path:
    seeds = simulate.load("seeds")["dev"]
    return write("dev", summarize("dev", seeds, run_world("dev", seeds, workers)))


def run_heldout(workers: int = 2) -> Path:
    if LOCK.exists():
        print(
            f"held-out seeds already ran ({LOCK.read_text().strip()}); new evidence needs new seeds and an ADR",
            file=sys.stderr,
        )
        raise SystemExit(3)
    seeds = simulate.load("seeds")["heldout"]
    REPORTS.mkdir(exist_ok=True)
    LOCK.write_text(json.dumps({"seeds": seeds, "config_hash": config_hash()}) + "\n")
    return write("heldout", summarize("heldout", seeds, run_world("heldout", seeds, workers)))
