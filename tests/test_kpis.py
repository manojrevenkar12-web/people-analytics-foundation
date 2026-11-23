"""KPIs as code and small-group privacy."""

import pandas as pd

from paf.lab import simulate
from paf.platform import kpis, records
from paf.world.truth import PeopleTeam


def platform_cells(W, cfg):  # type: ignore[no-untyped-def]
    m = records.build(W.exports, cfg, records.Switches(), PeopleTeam(W.company, W.keys), W.company.start, W.end)
    comp = kpis.components(m, cfg, W.company.start, W.company.months)
    return kpis.kpi_cells(comp, kpis.ttf_rows(m, W.company.start, W.company.months), cfg, "official", m.learned_teams)


def test_ratios_are_computed_from_sums_not_averaged(W) -> None:  # type: ignore[no-untyped-def]
    t = W.truth_cells
    m = 30
    co = t[(t.kpi == "underpaid_share") & (t.level == "company") & (t.m == m)]["value"].iloc[0]
    teams = t[(t.kpi == "underpaid_share") & (t.level == "team") & (t.m == m) & (t.population > 0)]
    weighted = (teams["value"] * teams["population"]).sum() / teams["population"].sum()
    assert abs(co - weighted) < 1e-9


def test_the_platform_matches_the_truth_on_headcount(W, cfg) -> None:  # type: ignore[no-untyped-def]
    cells = platform_cells(W, cfg)
    a = cells[(cells.kpi == "headcount") & (cells.level == "company")].set_index("m")["value"]
    b = W.truth_cells[(W.truth_cells.kpi == "headcount") & (W.truth_cells.level == "company")].set_index("m")["value"]
    assert (a == b).all()


def test_no_small_group_is_published_or_derivable(W, cfg) -> None:  # type: ignore[no-untyped-def]
    cells = kpis.protect(platform_cells(W, cfg), 5, True)
    assert not (cells["published"] & (cells["population"] < 5)).any()
    assert simulate.disclosures(cells, 5)["total"] == 0
    weak = kpis.protect(platform_cells(W, cfg), 5, False)
    assert simulate.disclosures(weak, 5)["by_subtraction"] > 0


def test_complementary_suppression_on_a_tiny_tree() -> None:
    rows = [
        {"kpi": "headcount", "level": "dept", "node": "D", "parent": "Company", "m": 0, "value": 23, "population": 23},
        {"kpi": "headcount", "level": "team", "node": "A", "parent": "D", "m": 0, "value": 3, "population": 3},
        {"kpi": "headcount", "level": "team", "node": "B", "parent": "D", "m": 0, "value": 8, "population": 8},
        {"kpi": "headcount", "level": "team", "node": "C", "parent": "D", "m": 0, "value": 12, "population": 12},
        {
            "kpi": "headcount",
            "level": "company",
            "node": "Company",
            "parent": "",
            "m": 0,
            "value": 23,
            "population": 23,
        },
    ]
    out = kpis.protect(pd.DataFrame(rows), 5, True).set_index("node")
    assert not out.loc["A", "published"] and not out.loc["B", "published"] and out.loc["C", "published"]
    assert out.loc["B", "why_hidden"] == "protects a small group"


def test_an_empty_cell_needs_no_protection() -> None:
    def cell(level: str, node: str, parent: str, n: int) -> dict:
        return {"kpi": "headcount", "level": level, "node": node, "parent": parent, "m": 0, "value": n, "population": n}

    rows = [
        cell("dept", "D", "Company", 20),
        cell("dept", "E", "Company", 30),
        cell("dept", "Unmapped", "Company", 0),
        cell("company", "Company", "", 50),
    ]
    out = kpis.protect(pd.DataFrame(rows), 5, True).set_index("node")
    assert out.loc["D", "published"] and out.loc["E", "published"]
    assert out.loc["Unmapped", "why_hidden"] == "nobody"
