"""The canonical model as it really is, built from the company itself, plus the People team's answers when the
platform asks. Only the lab reads this module.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from paf.platform.records import Model
from paf.world.company import Company, month_end, month_start
from paf.world.systems import Keys


def true_model(company: Company) -> Model:
    last = month_end(company.start, company.months - 1)
    w, o, c, lv = [], [], [], []
    for e in company.jobs.values():
        exit_d = e.exit if e.exit and e.exit <= last else None
        w.append(
            {
                "worker_key": str(e.eid),
                "kind": e.kind,
                "country": e.country,
                "hire": e.hire,
                "exit": exit_d,
                "exit_kind": e.exit_kind if exit_d else None,
                "regrettable": e.regrettable if exit_d else None,
                "fte": e.fte,
                "visible_from": None,
                "visible_to": None,
            }
        )
        for when, team in e.team_history:
            o.append({"worker_key": str(e.eid), "valid_from": when, "team": team})
        for when, sal in e.salary_history:
            c.append({"worker_key": str(e.eid), "valid_from": when, "salary": sal, "level": e.level_on(when)})
        for a, b in e.leaves:
            lv.append({"worker_key": str(e.eid), "start": a, "end": b})
    reqs = []
    for r in company.reqs.values():
        if r.opened > last:
            continue
        if r.filled and r.filled <= last:
            status, closed = "filled", r.filled
        elif r.cancelled and r.cancelled <= last:
            status, closed = "closed", r.cancelled
        else:
            status, closed = "open", None
        reqs.append(
            {
                "req_id": f"REQ-{r.rid:04d}",
                "team": r.team,
                "family": r.family,
                "opened": r.opened,
                "status": status,
                "closed": closed,
                "offers": r.offers,
            }
        )
    return Model(
        pd.DataFrame(w),
        pd.DataFrame(o),
        pd.DataFrame(c),
        pd.DataFrame(lv, columns=["worker_key", "start", "end"]),
        pd.DataFrame(reqs),
    )


class PeopleTeam:
    """Answers the platform's review questions from the employee file (the truth)."""

    def __init__(self, company: Company, keys: Keys) -> None:
        self.company = company
        self.by_old = {str(v): e for e, v in keys.old_nr.items()}
        self.by_new = {v: e for e, v in keys.new_id.items()}
        self.last = month_end(company.start, company.months - 1)

    def _job(self, source: str, sid: str):  # type: ignore[no-untyped-def]
        eid = (self.by_old if source == "old" else self.by_new).get(sid)
        return self.company.jobs[eid] if eid else None

    def exit_of(self, source: str, source_id: str) -> dict | None:
        e = self._job(source, source_id)
        if e is None or e.exit is None or e.exit > self.last:
            return None
        return {"exit": e.exit, "exit_kind": e.exit_kind}

    def leave_of(self, source: str, source_id: str, month: date) -> tuple[date, date] | None:
        e = self._job(source, source_id)
        if e is None:
            return None
        for a, b in e.leaves:
            if a <= month_end(self.company.start, _m(self.company, month)) and b >= month:
                return (a, b)
        return None

    def code_exit(self, response_id: str, keys: Keys, seed: int, error: float = 0.05) -> str:
        """A person reading the comment and coding it by hand: right nearly every time."""
        from paf.world import luck

        reason = keys.survey_truth[response_id]
        if luck.uniform(seed, "manualcode", response_id) < error:
            return "culture" if reason != "culture" else "role_fit"
        return reason

    def department_of(self, team_code: str) -> str:
        for t in self.company.teams:
            if t["code"] == team_code:
                return str(t["dept"])
        return "Unmapped"

    def team_for(self, department_name: str) -> str:
        for t in self.company.teams:
            if department_name in (t["old"], t.get("renamed_to"), t["code"]):
                return str(t["code"])
        return "UNMAPPED"


def _m(company: Company, d: date) -> int:
    return (d.year - company.start.year) * 12 + d.month - company.start.month


__all__ = ["PeopleTeam", "month_start", "true_model"]
