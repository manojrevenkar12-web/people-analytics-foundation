"""KPIs as code: additive components counted per team and month in SQL (DuckDB), summed up the org tree, turned
into each catalogue KPI at every level, then checked for privacy before anything is published.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd

from paf.platform.records import Model

COMPONENTS_SQL = """
WITH months AS (
  SELECT m, month_start, month_end FROM cal
),
wm AS (
  SELECT w.worker_key, w.kind, w.country, w.fte, mo.m, mo.month_end AS d
  FROM workers w JOIN months mo
    ON w.hire <= mo.month_end
   AND (w.exit IS NULL OR w.exit >= mo.month_end)
   AND (w.visible_from IS NULL OR mo.month_end >= w.visible_from)
   AND (w.visible_to IS NULL OR mo.month_end <= w.visible_to)
  WHERE w.kind <> 'contractor'
),
wm_team AS (
  SELECT wm.*, (
    SELECT o.team FROM org o WHERE o.worker_key = wm.worker_key AND o.valid_from <= wm.d
    ORDER BY o.valid_from DESC LIMIT 1) AS team_now,
    (SELECT o.team FROM org o WHERE o.worker_key = wm.worker_key ORDER BY o.valid_from LIMIT 1) AS team_first,
    (SELECT c.salary FROM comp c WHERE c.worker_key = wm.worker_key AND c.valid_from <= wm.d
     ORDER BY c.valid_from DESC LIMIT 1) AS salary,
    (SELECT c.level FROM comp c WHERE c.worker_key = wm.worker_key AND c.valid_from <= wm.d
     ORDER BY c.valid_from DESC LIMIT 1) AS level
  FROM wm
),
heads AS (
  SELECT COALESCE(team_now, team_first, 'UNMAPPED') AS team, m, COUNT(*) AS hc, SUM(fte) AS fte,
         SUM(CASE WHEN salary IS NOT NULL AND level IS NOT NULL
                   AND salary < 0.9 * band_mid(level, country) THEN 1 ELSE 0 END) AS underpaid
  FROM wm_team GROUP BY 1, 2
),
events AS (
  SELECT w.*, mo.m,
    (SELECT o.team FROM org o WHERE o.worker_key = w.worker_key ORDER BY o.valid_from LIMIT 1) AS team_first
  FROM workers w JOIN months mo ON 1 = 1
  WHERE w.kind <> 'contractor'
),
hires AS (
  SELECT COALESCE((SELECT o.team FROM org o WHERE o.worker_key = e.worker_key AND o.valid_from <= e.hire
                   ORDER BY o.valid_from DESC LIMIT 1), e.team_first, 'UNMAPPED') AS team, e.m, COUNT(*) AS hires
  FROM events e, months mo
  WHERE mo.m = e.m AND e.hire BETWEEN mo.month_start AND mo.month_end
    AND (e.visible_from IS NULL OR e.hire >= e.visible_from) AND (e.visible_to IS NULL OR e.hire <= e.visible_to)
  GROUP BY 1, 2
),
exits AS (
  SELECT COALESCE((SELECT o.team FROM org o WHERE o.worker_key = e.worker_key AND o.valid_from <= e.exit
                   ORDER BY o.valid_from DESC LIMIT 1), e.team_first, 'UNMAPPED') AS team, e.m,
         SUM(CASE WHEN e.exit_kind = 'voluntary' THEN 1 ELSE 0 END) AS vol_exits,
         COUNT(*) AS all_exits,
         SUM(CASE WHEN e.exit - e.hire < 90 THEN 1 ELSE 0 END) AS early_exits
  FROM events e, months mo
  WHERE mo.m = e.m AND e.exit BETWEEN mo.month_start AND mo.month_end
    AND (e.visible_from IS NULL OR e.exit >= e.visible_from) AND (e.visible_to IS NULL OR e.exit <= e.visible_to)
  GROUP BY 1, 2
),
open_reqs AS (
  SELECT r.team, mo.m, COUNT(*) AS open_reqs
  FROM reqs r JOIN months mo ON r.opened <= mo.month_end AND (r.closed IS NULL OR r.closed > mo.month_end)
  GROUP BY 1, 2
)
SELECT g.team, g.m,
       COALESCE(h.hc, 0) AS hc, COALESCE(h.fte, 0) AS fte, COALESCE(h.underpaid, 0) AS underpaid,
       COALESCE(hi.hires, 0) AS hires, COALESCE(x.vol_exits, 0) AS vol_exits, COALESCE(x.all_exits, 0) AS all_exits,
       COALESCE(x.early_exits, 0) AS early_exits, COALESCE(o.open_reqs, 0) AS open_reqs
FROM (SELECT t.team, mo.m FROM teams t, months mo) g
LEFT JOIN heads h ON h.team = g.team AND h.m = g.m
LEFT JOIN hires hi ON hi.team = g.team AND hi.m = g.m
LEFT JOIN exits x ON x.team = g.team AND x.m = g.m
LEFT JOIN open_reqs o ON o.team = g.team AND o.m = g.m
ORDER BY g.team, g.m
"""


def calendar(start: date, months: int) -> pd.DataFrame:
    rows = []
    for m in range(months):
        y, mo = start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1
        ms = date(y, mo, 1)
        me = (ms + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        rows.append({"m": m, "month_start": ms, "month_end": me})
    return pd.DataFrame(rows)


def components(model: Model, cfg: dict, start: date, months: int) -> pd.DataFrame:
    """Additive counts per team and month."""
    con = duckdb.connect()
    bands = cfg["bands"]

    def band_mid(level: int, country: str) -> float:
        return float(bands["level_mid"][int(level)]) * float(bands["country"].get(country, 1.0))

    con.create_function("band_mid", band_mid, ["BIGINT", "VARCHAR"], "DOUBLE")
    teams = sorted(set(cfg["org"]["teams"]) | set(model.org["team"].unique() if len(model.org) else []) | {"UNMAPPED"})
    con.register("cal", calendar(start, months))
    con.register("workers", model.workers)
    con.register("org", model.org)
    con.register("comp", model.comp)
    con.register("reqs", model.reqs.assign(closed=model.reqs["closed"].where(model.reqs["closed"].notna(), None)))
    con.register("teams", pd.DataFrame({"team": teams}))
    out = con.execute(COMPONENTS_SQL).df()
    con.close()
    return out


def ttf_rows(model: Model, start: date, months: int) -> pd.DataFrame:
    cal = calendar(start, months)
    r = model.reqs[(model.reqs["status"] == "filled") & model.reqs["closed"].notna()].copy()
    r["days"] = [(c - o).days for c, o in zip(r["closed"], r["opened"], strict=True)]
    r["m"] = [int((c.year - start.year) * 12 + c.month - start.month) for c in r["closed"]]
    r = r[(r["m"] >= 0) & (r["m"] < len(cal))]
    return r[["team", "m", "days"]]


def tree(cfg: dict, teams: list[str], learned: dict[str, str] | None = None) -> dict[str, tuple[str, str]]:
    """team -> (dept, company)"""
    m = {**dict(cfg["org"]["teams"]), **(learned or {})}
    return {t: (m.get(t, "Unmapped"), "Company") for t in teams}


def kpi_cells(
    comp: pd.DataFrame,
    ttf: pd.DataFrame,
    cfg: dict,
    definitions: str = "official",
    learned: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Every KPI at team, department and company level for every month, before privacy."""
    teams = sorted(comp["team"].unique())
    tr = tree(cfg, teams, learned)
    comp = comp.assign(dept=comp["team"].map(lambda t: tr[t][0]))
    cols = ["hc", "fte", "underpaid", "hires", "vol_exits", "all_exits", "early_exits", "open_reqs"]
    frames = [
        comp.assign(level="team", node=comp["team"], parent=comp["dept"])[["level", "node", "parent", "m", *cols]]
    ]
    d = comp.groupby(["dept", "m"], as_index=False)[cols].sum()
    frames.append(d.assign(level="dept", node=d["dept"], parent="Company")[["level", "node", "parent", "m", *cols]])
    c = comp.groupby(["m"], as_index=False)[cols].sum()
    frames.append(c.assign(level="company", node="Company", parent="")[["level", "node", "parent", "m", *cols]])
    agg = pd.concat(frames, ignore_index=True).sort_values(["level", "node", "m"])
    g = agg.groupby(["level", "node"])
    agg["vol_12m"] = g["vol_exits"].transform(lambda s: s.rolling(12, min_periods=1).sum())
    agg["all_12m"] = g["all_exits"].transform(lambda s: s.rolling(12, min_periods=1).sum())
    agg["avg_hc_12m"] = g["hc"].transform(lambda s: s.rolling(12, min_periods=1).mean())

    ttf = ttf.assign(dept=ttf["team"].map(lambda t: tr.get(t, ("Unmapped", "Company"))[0]))
    rows = []
    for r in agg.itertuples(index=False):
        if definitions == "analyst":  # every leaver over the month-end headcount
            turnover = r.all_12m / r.hc if r.hc else np.nan
        else:
            turnover = r.vol_12m / r.avg_hc_12m if r.avg_hc_12m else np.nan
        if r.level == "team":
            sel = ttf[(ttf["team"] == r.node) & (ttf["m"] > r.m - 3) & (ttf["m"] <= r.m)]
        elif r.level == "dept":
            sel = ttf[(ttf["dept"] == r.node) & (ttf["m"] > r.m - 3) & (ttf["m"] <= r.m)]
        else:
            sel = ttf[(ttf["m"] > r.m - 3) & (ttf["m"] <= r.m)]
        values = {
            "headcount": r.hc,
            "fte": r.fte,
            "hires": r.hires,
            "voluntary_turnover_12m": turnover,
            "new_hire_exits_90d": r.early_exits,
            "underpaid_share": (r.underpaid / r.hc) if r.hc else np.nan,
            "open_reqs": r.open_reqs,
            "time_to_fill_median": float(sel["days"].median()) if len(sel) else np.nan,
        }
        for k, v in values.items():
            rows.append(
                {
                    "kpi": k,
                    "level": r.level,
                    "node": r.node,
                    "parent": r.parent,
                    "m": r.m,
                    "value": v,
                    "population": int(r.hc),
                }
            )
    return pd.DataFrame(rows)


ADDITIVE = {"headcount", "fte", "hires", "new_hire_exits_90d", "open_reqs"}


def protect(cells: pd.DataFrame, min_group: int, complementary: bool) -> pd.DataFrame:
    """Hide every cell about fewer than `min_group` people; then, where a parent is shown and exactly one of its
    children is hidden, hide the smallest other child too, so the hidden one cannot be worked out by subtraction."""
    cells = cells.copy()
    cells["published"] = cells["population"] >= min_group
    cells["why_hidden"] = np.where(cells["published"], "", np.where(cells["population"] == 0, "nobody", "small group"))
    if complementary:
        for _ in range(4):
            changed = False
            for _key, grp in cells[cells["level"] != "company"].groupby(["kpi", "m", "parent"]):
                # an empty cell is about nobody: it hides nothing and needs no protection
                hidden = grp[~grp["published"] & (grp["population"] > 0)]
                shown = grp[grp["published"]]
                if len(hidden) == 1 and len(shown) >= 1:
                    victim = shown.sort_values("population").index[0]
                    cells.loc[victim, ["published", "why_hidden"]] = [False, "protects a small group"]
                    changed = True
            if not changed:
                break
    return cells
