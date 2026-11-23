"""Forecasts from the canonical model, each checked against a naive baseline at rolling origins.

Retention: a logistic model of a voluntary exit in a person-month (tenure, pay against band, production in the
fourth quarter, the team's recent exits), summed over who is employed at the origin, six months ahead, by department.
Hiring: Kaplan-Meier time-to-fill by job family over requisitions known at the origin, turned into how many of the
open requisitions will be filled in the next 90 days.
Only data dated on or before the origin is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypeVar

import numpy as np
import pandas as pd

from paf.platform.kpis import calendar
from paf.platform.records import Model


@dataclass
class Panel:
    x: np.ndarray
    y: np.ndarray
    dept: np.ndarray
    m: np.ndarray
    key: np.ndarray


def _team_at(org: pd.DataFrame) -> dict[str, list[tuple[date, str]]]:
    out: dict[str, list[tuple[date, str]]] = {}
    for r in org.sort_values("valid_from").itertuples(index=False):
        out.setdefault(r.worker_key, []).append((r.valid_from, r.team))
    return out


T = TypeVar("T")


def _at(rows: list[tuple[date, T]], d: date) -> T | None:
    v = rows[0][1] if rows else None
    for when, x in rows:
        if when <= d:
            v = x
    return v


def panel(model: Model, cfg: dict, start: date, months: int) -> Panel:
    teams = dict(cfg["org"]["teams"]) | dict(model.learned_teams)
    bands = cfg["bands"]
    org = _team_at(model.org)
    comp: dict[str, list[tuple[date, tuple[float, int]]]] = {}
    for r in model.comp.sort_values("valid_from").itertuples(index=False):
        comp.setdefault(r.worker_key, []).append((r.valid_from, (r.salary, r.level)))
    cal = calendar(start, months)
    rows, ys, ds, ms, ks = [], [], [], [], []
    # trailing team exit rate, from the same data
    exits_by_team_month: dict[tuple[str, int], int] = {}
    hc_by_team_month: dict[tuple[str, int], int] = {}
    w = model.workers[model.workers["kind"] != "contractor"]
    for r in w.itertuples(index=False):
        for c in cal.itertuples(index=False):
            vis_ok = (r.visible_from is None or pd.isna(r.visible_from) or c.month_end >= r.visible_from) and (
                r.visible_to is None or pd.isna(r.visible_to) or c.month_end <= r.visible_to
            )
            if not vis_ok or r.hire > c.month_end:
                continue
            ex = r.exit if (r.exit is not None and not pd.isna(r.exit)) else None
            if ex is not None and ex < c.month_start:
                continue
            team = _at(org.get(r.worker_key, []), c.month_end) or "UNMAPPED"
            leaves = ex is not None and c.month_start <= ex <= c.month_end and r.exit_kind == "voluntary"
            hc_by_team_month[(str(team), c.m)] = hc_by_team_month.get((str(team), c.m), 0) + 1
            if leaves:
                exits_by_team_month[(str(team), c.m)] = exits_by_team_month.get((str(team), c.m), 0) + 1
            sal_lv = _at(comp.get(r.worker_key, []), c.month_end)
            under = 0.0
            if sal_lv is not None:
                sal, lv = sal_lv
                mid = float(bands["level_mid"][int(lv)]) * float(bands["country"].get(r.country, 1.0))
                under = 1.0 if sal < 0.9 * mid else 0.0
            tenure_days = (c.month_start - r.hire).days
            dept = teams.get(str(team), "Unmapped")
            rows.append(
                [
                    1.0,
                    1.0 if tenure_days < 182 else 0.0,
                    under,
                    1.0 if (dept == "Production" and c.month_start.month >= 9) else 0.0,
                    0.0,
                ]
            )
            ys.append(1.0 if leaves else 0.0)
            ds.append(dept)
            ms.append(c.m)
            ks.append(str(team))
    x = np.array(rows)
    # feature 4: the team's voluntary exit rate over the previous 12 months
    for i, (team, m) in enumerate(zip(ks, ms, strict=True)):
        e = sum(exits_by_team_month.get((team, j), 0) for j in range(max(0, m - 12), m))
        h = sum(hc_by_team_month.get((team, j), 0) for j in range(max(0, m - 12), m))
        x[i, 4] = 12.0 * e / h if h else 0.0
    return Panel(x, np.array(ys), np.array(ds), np.array(ms), np.array(ks))


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 25) -> np.ndarray:
    beta = np.zeros(x.shape[1])
    beta[0] = np.log(max(y.mean(), 1e-4) / max(1 - y.mean(), 1e-4))
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(x @ beta)))
        g = x.T @ (p - y) + l2 * np.r_[0.0, beta[1:]]
        h = (x * (p * (1 - p))[:, None]).T @ x + l2 * np.diag(np.r_[0.0, np.ones(len(beta) - 1)])
        step = np.linalg.solve(h + 1e-9 * np.eye(len(beta)), g)
        beta -= step
        if np.abs(step).max() < 1e-7:
            break
    return beta


def retention(pnl: Panel, origins: list[int], horizon: int, naive: bool, start_month: int = 12) -> pd.DataFrame:
    """Predicted voluntary exits per department in months (origin, origin + horizon]."""
    out = []
    for o in origins:
        train = pnl.m < o
        at = pnl.m == o
        if naive or train.sum() < 100:
            for dept in sorted(set(pnl.dept)):
                mask = (pnl.dept == dept) & (pnl.m < o) & (pnl.m >= o - 12)
                rate = pnl.y[mask].sum() / max(1, len(set(pnl.m[mask])))
                out.append({"origin": o, "dept": dept, "predicted": rate * horizon})
            continue
        beta = fit_logistic(pnl.x[train], pnl.y[train])
        x0 = pnl.x[at].copy()
        for dept in sorted(set(pnl.dept)):
            sel = pnl.dept[at] == dept
            total = 0.0
            for step in range(1, horizon + 1):
                xs = x0[sel].copy()
                # tenure moves on; the fourth-quarter flag follows the calendar of the future month
                xs[:, 1] = np.where(xs[:, 1] > 0, (step < 6) * 1.0, 0.0)
                calendar_month = (start_month - 1 + o + step) % 12 + 1
                q4 = 1.0 if calendar_month >= 9 else 0.0
                xs[:, 3] = q4 if dept == "Production" else 0.0
                total += float((1 / (1 + np.exp(-(xs @ beta)))).sum())
            out.append({"origin": o, "dept": dept, "predicted": total})
    return pd.DataFrame(out)


def realised_exits(pnl: Panel, origins: list[int], horizon: int) -> pd.DataFrame:
    out = []
    for o in origins:
        for dept in sorted(set(pnl.dept)):
            mask = (pnl.dept == dept) & (pnl.m > o) & (pnl.m <= o + horizon)
            out.append({"origin": o, "dept": dept, "actual": float(pnl.y[mask].sum())})
    return pd.DataFrame(out)


def _km(durations: np.ndarray, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(durations)
    t, e = durations[order], events[order]
    times, surv, s, n = [0.0], [1.0], 1.0, len(t)
    i = 0
    while i < len(t):
        j = i
        while j < len(t) and t[j] == t[i]:
            j += 1
        d = int(e[i:j].sum())
        if d:
            s *= 1 - d / n
            times.append(float(t[i]))
            surv.append(s)
        n -= j - i
        i = j
    return np.array(times), np.array(surv)


def _s(times: np.ndarray, surv: np.ndarray, x: float) -> float:
    k = np.searchsorted(times, x, side="right") - 1
    return float(surv[max(0, int(k))])


def hiring(reqs: pd.DataFrame, start: date, origins: list[int], horizon_days: int, naive: bool) -> pd.DataFrame:
    cal = calendar(start, max(origins) + 4)
    out = []
    for o in origins:
        d = cal.loc[cal["m"] == o, "month_end"].iloc[0]
        known = reqs[reqs["opened"] <= d]
        for fam in sorted(reqs["family"].unique()):
            k = known[known["family"] == fam]
            if naive:
                recent = k[(k["status"] == "filled") & k["closed"].notna()]
                recent = recent[(recent["closed"] <= d) & (recent["closed"] > d - timedelta(days=horizon_days))]
                out.append({"origin": o, "family": fam, "predicted": float(len(recent))})
                continue
            dur, ev = [], []
            for r in k.itertuples(index=False):
                closed = r.closed if (r.closed is not None and not pd.isna(r.closed) and r.closed <= d) else None
                if closed is not None:
                    dur.append((closed - r.opened).days)
                    ev.append(1 if r.status == "filled" else 0)
                else:
                    dur.append((d - r.opened).days)
                    ev.append(0)
            if not dur:
                out.append({"origin": o, "family": fam, "predicted": 0.0})
                continue
            times, surv = _km(np.array(dur, float), np.array(ev, float))
            done = [e for e in ev]
            cancel_share = 1 - (
                sum(done)
                / max(
                    1,
                    sum(
                        1
                        for r in k.itertuples(index=False)
                        if r.closed is not None and not pd.isna(r.closed) and r.closed <= d
                    ),
                )
            )
            total = 0.0
            for r in k.itertuples(index=False):
                is_open = r.closed is None or pd.isna(r.closed) or r.closed > d
                if not is_open:
                    continue
                age = (d - r.opened).days
                s_now = _s(times, surv, age)
                if s_now <= 0:
                    continue
                total += (s_now - _s(times, surv, age + horizon_days)) / s_now * (1 - cancel_share)
            out.append({"origin": o, "family": fam, "predicted": total})
    return pd.DataFrame(out)


def realised_fills(reqs: pd.DataFrame, start: date, origins: list[int], horizon_days: int) -> pd.DataFrame:
    cal = calendar(start, max(origins) + 4)
    out = []
    for o in origins:
        d = cal.loc[cal["m"] == o, "month_end"].iloc[0]
        for fam in sorted(reqs["family"].unique()):
            f = reqs[(reqs["family"] == fam) & (reqs["status"] == "filled") & reqs["closed"].notna()]
            n = int(((f["closed"] > d) & (f["closed"] <= d + timedelta(days=horizon_days))).sum())
            out.append({"origin": o, "family": fam, "actual": float(n)})
    return pd.DataFrame(out)
