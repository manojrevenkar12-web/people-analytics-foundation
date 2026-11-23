"""Run one design through one world and grade it against the truth.

The design reads the systems' exports through the platform with its switches; the evaluation reads the truth: the
true canonical model, the real reasons people left, the right answers to their questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from paf.platform import forecast as fc
from paf.platform import kpis, pilots, records
from paf.world.company import Company, month_end, simulate
from paf.world.reader_sim import SimReader
from paf.world.systems import Exports, Keys, record
from paf.world.texts import write
from paf.world.truth import PeopleTeam, true_model

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config"


def load(name: str) -> Any:
    return yaml.safe_load((CONFIG / f"{name}.yml").read_text())


def merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def designs() -> dict[str, dict]:
    d = load("designs")
    out = {"status_quo": d["status_quo"], "platform": d["platform"]}
    out["model_alone"] = merge(d["platform"], d["model_alone"]["overlay"]) | {"label": d["model_alone"]["label"]}
    for name, a in d["ablations"].items():
        out[name] = merge(d["platform"], a["overlay"]) | {"label": a["label"]}
    return out


@dataclass
class World:
    company: Company
    exports: Exports
    keys: Keys
    truth_cells: pd.DataFrame
    truth_panel: fc.Panel
    truth_reqs: pd.DataFrame
    end: date


@lru_cache(maxsize=8)
def world(world_name: str, seed: int) -> World:
    w = load("world")
    cfg = load("platform")
    c = simulate(seed, w, world_name)
    x, k = record(c, w, world_name, seed)
    write(c, w, world_name, seed, x, k)
    tm = true_model(c)
    tm.learned_teams = {t["code"]: t["dept"] for t in c.teams}
    comp = kpis.components(tm, cfg, c.start, c.months)
    cells = kpis.kpi_cells(comp, kpis.ttf_rows(tm, c.start, c.months), cfg, "official", tm.learned_teams)
    return World(c, x, k, cells, fc.panel(tm, cfg, c.start, c.months), tm.reqs, month_end(c.start, c.months - 1))


TOL = {
    "headcount": 0.5,
    "fte": 0.5,
    "hires": 0.5,
    "new_hire_exits_90d": 0.5,
    "open_reqs": 0.5,
    "voluntary_turnover_12m": 0.005,
    "underpaid_share": 0.01,
    "time_to_fill_median": 1.0,
}


def kpi_accuracy(published: pd.DataFrame, truth: pd.DataFrame) -> dict:
    keys = ["kpi", "level", "node", "m"]
    p = published[published["published"]][[*keys, "value"]]
    t = truth[[*keys, "value"]].rename(columns={"value": "truth"})
    j = p.merge(t, on=keys, how="left")
    both_nan = j["value"].isna() & j["truth"].isna()
    err = (j["value"] - j["truth"]).abs()
    ok = both_nan | (err <= j["kpi"].map(TOL))
    j["ok"] = ok
    co = j[j["level"] == "company"]
    by_kpi = {k: float(g["ok"].mean()) for k, g in j.groupby("kpi")}
    return {
        "cells": len(j),
        "correct_share": float(ok.mean()),
        "wrong_cells": int((~ok).sum()),
        "company_correct_share": float(co["ok"].mean()) if len(co) else float("nan"),
        "by_kpi": by_kpi,
    }


def disclosures(cells: pd.DataFrame, min_group: int) -> dict:
    """What an attacker with the published table learns about groups smaller than `min_group`."""
    direct = int((cells["published"] & (cells["population"] < min_group) & (cells["level"] != "company")).sum())
    derived = 0
    pub = cells.set_index(["kpi", "level", "node", "m"])
    for (kpi, m, parent), grp in cells[cells["level"] != "company"].groupby(["kpi", "m", "parent"]):
        if kpi not in kpis.ADDITIVE:
            continue
        hidden = grp[~grp["published"] & (grp["population"] > 0)]
        if len(hidden) != 1:
            continue
        plevel = "company" if parent == "Company" else "dept"
        try:
            parent_row = pub.loc[(kpi, plevel, parent, m)]
        except KeyError:
            continue
        if bool(parent_row["published"]) and int(hidden["population"].iloc[0]) < min_group:
            derived += 1
    return {"direct": direct, "by_subtraction": derived, "total": direct + derived}


def run(world_name: str, seed: int, name: str, design: dict) -> dict:
    cfg = load("platform")
    w = load("world")
    W = world(world_name, seed)
    c = W.company
    pt = PeopleTeam(c, W.keys)
    data = design["data"]
    sw = records.Switches(identity=data["identity"], quality=data["quality"], rename_map=data["rename_map"])
    model = records.build(W.exports, cfg, sw, pt if sw.quality else None, c.start, W.end)

    # KPIs, privacy
    comp = kpis.components(model, cfg, c.start, c.months)
    cells = kpis.kpi_cells(
        comp, kpis.ttf_rows(model, c.start, c.months), cfg, design["definitions"], model.learned_teams
    )
    k_min = int(cfg["privacy"]["min_group"])
    if design["privacy"] == "none":
        cells = cells.assign(published=True, why_hidden="")
    else:
        cells = kpis.protect(cells, k_min, design["privacy"] == "complementary")
    acc = kpi_accuracy(cells, W.truth_cells)
    leak = disclosures(cells, k_min)

    # forecasts
    f = cfg["forecast"]
    origins, horizon = list(f["origins"]), int(f["retention_horizon_months"])
    naive = design["forecast"] == "naive"
    pnl = fc.panel(model, cfg, c.start, c.months)
    ret = (
        fc.retention(pnl, origins, horizon, naive, c.start.month)
        .merge(fc.realised_exits(W.truth_panel, origins, horizon), on=["origin", "dept"], how="right")
        .fillna({"predicted": 0.0})
    )
    ret_naive = (
        fc.retention(pnl, origins, horizon, True, c.start.month)
        .merge(fc.realised_exits(W.truth_panel, origins, horizon), on=["origin", "dept"], how="right")
        .fillna({"predicted": 0.0})
    )
    hdays = int(f["hiring_horizon_days"])
    fills = fc.realised_fills(W.truth_reqs, c.start, origins, hdays)
    hir = (
        fc.hiring(model.reqs, c.start, origins, hdays, naive)
        .merge(fills, on=["origin", "family"], how="right")
        .fillna({"predicted": 0.0})
    )
    hir_naive = (
        fc.hiring(model.reqs, c.start, origins, hdays, True)
        .merge(fills, on=["origin", "family"], how="right")
        .fillna({"predicted": 0.0})
    )

    # pilots
    pil = helpdesk(W, cfg, w, world_name, seed, design)
    ex = exit_coding(W, cfg, w, world_name, seed, design, pt)

    # reporting effort per month
    rep = cfg["reporting"]
    leaders = len(c.teams) + len({t["dept"] for t in c.teams})
    req_month = leaders * float(w["leaders"]["requests_per_leader_month"])
    cat = float(w["leaders"]["catalogue_share"])
    if name == "status_quo" or (design["privacy"] == "none" and design["definitions"] == "analyst"):
        analyst_h = float(rep["monthly_pack_hours"]) + req_month * float(rep["request_minutes"]) / 60
        leader_wait_share = 1.0
    else:
        analyst_h = req_month * (1 - cat) * float(rep["request_minutes"]) / 60 + model.review_minutes / 60 / c.months
        leader_wait_share = 1 - cat

    co_truth = W.truth_cells[(W.truth_cells["level"] == "company") & (W.truth_cells["kpi"] == "headcount")]
    co_design = cells[(cells["level"] == "company") & (cells["kpi"] == "headcount")]
    return {
        "design": name,
        "seed": seed,
        "label": design["label"],
        "kpi": acc,
        "disclosures": leak,
        "corrections": model.corrections,
        "issues": len(model.issues),
        "review_minutes": model.review_minutes,
        "retention_mae": float((ret["predicted"] - ret["actual"]).abs().mean()),
        "retention_naive_mae": float((ret_naive["predicted"] - ret_naive["actual"]).abs().mean()),
        "hiring_mae": float((hir["predicted"] - hir["actual"]).abs().mean()),
        "hiring_naive_mae": float((hir_naive["predicted"] - hir_naive["actual"]).abs().mean()),
        "helpdesk": pil,
        "exit_coding": ex,
        "analyst_hours_month": analyst_h,
        "leader_requests_waiting_share": leader_wait_share,
        "series": {
            "truth_headcount": [float(v) for v in co_truth.sort_values("m")["value"]],
            "headcount": [float(v) for v in co_design.sort_values("m")["value"]],
            "retention": ret.groupby("origin")[["predicted", "actual"]].sum().reset_index().to_dict("records"),
            "hiring": hir.groupby("origin")[["predicted", "actual"]].sum().reset_index().to_dict("records"),
        },
        "privacy_view": privacy_view(cells, c.months - 1),
        "issues_sample": [vars(i) for i in model.issues[:12]],
    }


def privacy_view(cells: pd.DataFrame, m: int) -> list[dict]:
    v = cells[(cells["kpi"] == "voluntary_turnover_12m") & (cells["m"] == m) & (cells["level"] != "company")]
    return [
        {
            "level": r.level,
            "node": r.node,
            "parent": r.parent,
            "value": None if pd.isna(r.value) else float(r.value),
            "population": int(r.population),
            "published": bool(r.published),
            "why": r.why_hidden,
        }
        for r in v.itertuples(index=False)
    ]


def helpdesk(W: World, cfg: dict, w: dict, world_name: str, seed: int, design: dict) -> dict:
    hd = cfg["helpdesk"]
    start_m, months = int(hd["pilot"]["start_month"]), int(hd["pilot"]["months"])
    tickets = W.exports.tickets
    truth = W.keys.ticket_truth
    mode = design["assistant"]
    if mode == "none":
        pilot = [t for t in tickets if start_m <= truth[t["ticket_id"]]["month"] < start_m + months]
        return {
            "run": False,
            "tickets": len(pilot),
            "people_minutes": float(sum(truth[t["ticket_id"]]["manual_minutes"] for t in pilot)),
            "wrong_rate": float(np.mean([truth[t["ticket_id"]]["manual_wrong"] for t in pilot])),
            "sensitive_read_by_model": 0,
        }
    guard = pilots.Guard(sensitive_rule=mode in ("guarded",), checks=mode in ("guarded", "no_sensitive_rule"))
    reader = SimReader(W.keys, w, world_name, seed)
    review = float(hd["minutes_review"])

    def outcomes(t: dict) -> tuple[dict, dict]:
        tr = truth[t["ticket_id"]]
        control = {"hours": tr["manual_hours"], "minutes": tr["manual_minutes"], "wrong": float(tr["manual_wrong"])}
        d = pilots.assistant_decision(t, reader, cfg, guard)
        if d["route"] == "sent":
            treated = {
                "hours": float(hd["answer_hours"]),
                "minutes": 0.0,
                "wrong": float(tr["sensitive"] or d["passage"] != tr["answer"]),
            }
        else:
            treated = {
                "hours": tr["manual_hours"],
                "minutes": tr["manual_minutes"] + (review if d["model_read"] else 0.0),
                "wrong": float(tr["manual_wrong"]),
            }
        treated["model_read_sensitive"] = float(d["model_read"] and tr["sensitive"])
        return treated, control

    pilot = [t for t in tickets if start_m <= truth[t["ticket_id"]]["month"] < start_m + months]
    before = [t for t in tickets if start_m - months <= truth[t["ticket_id"]]["month"] < start_m]
    pairs = [outcomes(t) for t in pilot]
    arm = np.array([pilots.treated(t["requester"], float(hd["pilot"]["treated_share"])) for t in pilot])
    groups = np.array([t["requester"] for t in pilot])
    res: dict[str, Any] = {"run": True, "tickets": len(pilot), "treated_share": float(arm.mean())}
    for metric in ("hours", "minutes", "wrong"):
        tre = np.array([p[0][metric] for p in pairs])
        con = np.array([p[1][metric] for p in pairs])
        true_effect = float((tre - con).mean())
        if design["evaluation"] == "randomised":
            est = pilots.diff_ci(tre[arm], con[~arm], groups[arm], groups[~arm])
        else:
            pre = np.array(
                [truth[t["ticket_id"]]["manual_" + ("wrong" if metric == "wrong" else metric)] for t in before], float
            )
            pre_g = np.array([t["requester"] for t in before])
            est = pilots.diff_ci(tre, pre, groups, pre_g)
        res[metric] = {
            "true_effect": true_effect,
            "estimate": est[0],
            "ci": [est[1], est[2]],
            "covered": bool(est[1] <= true_effect <= est[2]),
            "error": est[0] - true_effect,
        }
    res["treated_wrong_rate"] = float(np.mean([p[0]["wrong"] for p in pairs]))
    res["control_wrong_rate"] = float(np.mean([p[1]["wrong"] for p in pairs]))
    res["sensitive_read_by_model"] = int(sum(p[0]["model_read_sensitive"] for p in pairs))
    res["people_minutes_if_rolled_out"] = float(sum(p[0]["minutes"] for p in pairs))
    res["people_minutes_manual"] = float(sum(p[1]["minutes"] for p in pairs))
    res["model_calls"] = reader.calls
    return res


def exit_coding(W: World, cfg: dict, w: dict, world_name: str, seed: int, design: dict, pt: PeopleTeam) -> dict:
    ec = cfg["exit_coding"]
    resp = W.exports.exit_survey
    truth = W.keys.survey_truth
    mode = design["exit_coding"]
    themes = list(ec["themes"])
    coded, minutes, by_model = {}, 0.0, 0
    reader = SimReader(W.keys, w, world_name, seed)
    for r in resp:
        rid = r["response_id"]
        if mode == "manual":
            coded[rid] = pt.code_exit(rid, W.keys, seed)
            minutes += float(ec["manual_minutes"])
            continue
        out = pilots.code_exit(r, reader, cfg, pilots.Guard(checks=mode == "guarded"))
        if out["by"] == "model":
            coded[rid] = out["theme"]
            by_model += 1
        else:
            coded[rid] = pt.code_exit(rid, W.keys, seed)
            minutes += float(ec["manual_minutes"]) + float(ec["review_minutes"])
    acc = float(np.mean([coded[r] == truth[r] for r in coded])) if coded else float("nan")
    true_share = {t: sum(1 for r in truth.values() if r == t) / max(1, len(truth)) for t in themes}
    est_share = {t: sum(1 for v in coded.values() if v == t) / max(1, len(coded)) for t in themes}
    return {
        "responses": len(resp),
        "accuracy": acc,
        "people_minutes": minutes,
        "by_model_share": by_model / max(1, len(resp)),
        "share_error": float(sum(abs(true_share[t] - est_share[t]) for t in themes) / 2),
        "true_share": true_share,
        "estimated_share": est_share,
    }
