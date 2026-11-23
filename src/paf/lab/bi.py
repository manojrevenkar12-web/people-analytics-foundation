"""Power BI files: a star schema of the platform's published KPI cells (privacy already applied) and DAX measures
generated from the KPI catalogue. Power BI only displays numbers the platform computed; it never recomputes them, so
the dashboard and the catalogue cannot disagree.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from paf.lab import simulate
from paf.platform import kpis, records
from paf.world.truth import PeopleTeam

MEASURE = """{name} =
CALCULATE ( [KPI value], dim_kpi[kpi_id] = "{id}" )
"""


def cells_for(seed: int) -> pd.DataFrame:
    cfg = simulate.load("platform")
    W = simulate.world("dev", seed)
    c = W.company
    model = records.build(W.exports, cfg, records.Switches(), PeopleTeam(c, W.keys), c.start, W.end)
    comp = kpis.components(model, cfg, c.start, c.months)
    cells = kpis.kpi_cells(comp, kpis.ttf_rows(model, c.start, c.months), cfg, "official", model.learned_teams)
    cells = kpis.protect(cells, int(cfg["privacy"]["min_group"]), bool(cfg["privacy"]["complementary"]))
    cal = kpis.calendar(c.start, c.months)
    return cells.merge(cal[["m", "month_start"]], on="m")


def export(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    seed = simulate.load("seeds")["dev"][0]
    cells = cells_for(seed)
    catalogue = yaml.safe_load((simulate.CONFIG / "kpis.yml").read_text())
    pub = cells[cells["published"]].copy()
    pub["value"] = pub["value"].round(4)
    pub[["kpi", "level", "node", "month_start", "value"]].rename(
        columns={"kpi": "kpi_id", "month_start": "month"}
    ).to_csv(out / "fact_kpi.csv", index=False, float_format="%.10g")
    org = cells[["level", "node", "parent"]].drop_duplicates().sort_values(["level", "node"])
    org.to_csv(out / "dim_org.csv", index=False, float_format="%.10g")
    cells[["month_start"]].drop_duplicates().rename(columns={"month_start": "month"}).sort_values("month").to_csv(
        out / "dim_month.csv", index=False
    )
    pd.DataFrame(
        [{k: v for k, v in kpi.items() if k in ("id", "name", "owner", "definition", "unit")} for kpi in catalogue]
    ).rename(columns={"id": "kpi_id"}).to_csv(out / "dim_kpi.csv", index=False, float_format="%.10g")
    dax = [
        "-- Generated from config/kpis.yml by `python -m paf.cli report`. Do not edit.",
        "-- One value per KPI, org node and month, already privacy-checked by the platform.",
        "",
        "KPI value =",
        "IF (",
        "    HASONEVALUE ( dim_kpi[kpi_id] ) && HASONEVALUE ( dim_org[node] ) && HASONEVALUE ( dim_month[month] ),",
        "    SELECTEDVALUE ( fact_kpi[value] )",
        ")",
        "",
    ]
    for kpi in catalogue:
        dax.append(MEASURE.format(name=kpi["name"], id=kpi["id"]))
    (out / "measures.dax").write_text("\n".join(dax))
