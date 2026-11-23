"""Forecasts use only what was known at the origin."""

import numpy as np

from paf.platform import forecast as fc
from paf.world.truth import true_model


def test_retention_ignores_the_future(W, cfg) -> None:  # type: ignore[no-untyped-def]
    p = fc.panel(true_model(W.company), cfg, W.company.start, W.company.months)
    a = fc.retention(p, [18], 6, False)
    q = fc.Panel(p.x.copy(), p.y.copy(), p.dept, p.m, p.key)
    q.y[q.m > 18] = 1 - q.y[q.m > 18]  # rewrite the future
    b = fc.retention(q, [18], 6, False)
    assert np.allclose(a["predicted"], b["predicted"])


def test_kaplan_meier_with_censoring() -> None:
    times, surv = fc._km(np.array([10.0, 20, 20, 30, 40]), np.array([1.0, 1, 0, 1, 0]))
    assert fc._s(times, surv, 5) == 1.0
    assert abs(fc._s(times, surv, 10) - 0.8) < 1e-9
    assert abs(fc._s(times, surv, 25) - 0.6) < 1e-9
    assert abs(fc._s(times, surv, 30) - 0.3) < 1e-9


def test_hiring_forecast_counts_only_open_requisitions_at_the_origin(W) -> None:  # type: ignore[no-untyped-def]
    reqs = W.truth_reqs
    f = fc.hiring(reqs, W.company.start, [20], 90, False)
    assert (f["predicted"] >= 0).all()
    open_at = reqs[(reqs["opened"] <= fc.calendar(W.company.start, 30)["month_end"][20])]
    assert f["predicted"].sum() <= len(open_at)
