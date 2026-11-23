"""From system exports to one HR data model.

Adapters read each system as it is and refuse what they do not know (an unknown department becomes an issue, never a
guess). Identity links a person's old-HRIS record to their new-HRIS record. Quality rules check the HRIS against
payroll and the ATS; what code can settle it settles, what it cannot goes to the People team. The result is the
canonical model every KPI, forecast and dashboard reads.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

import pandas as pd


class Reviewer(Protocol):
    """The People team: looks at the contract and the employee file and says what is true."""

    def exit_of(self, source: str, source_id: str) -> dict | None: ...
    def leave_of(self, source: str, source_id: str, month: date) -> tuple[date, date] | None: ...
    def team_for(self, department_name: str) -> str: ...
    def department_of(self, team_code: str) -> str: ...


@dataclass
class Switches:
    identity: bool = True
    quality: bool = True
    rename_map: bool = True  # the department map knows every name the old HRIS used


@dataclass
class Issue:
    rule: str
    worker_key: str
    detail: str
    resolved: str = ""


@dataclass
class Model:
    workers: pd.DataFrame
    org: pd.DataFrame
    comp: pd.DataFrame
    leaves: pd.DataFrame
    reqs: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    corrections: dict[str, int] = field(default_factory=dict)
    review_minutes: float = 0.0
    learned_teams: dict[str, str] = field(default_factory=dict)  # team code -> department, from review


def _de(s: str) -> date | None:
    if not s:
        return None
    d, m, y = s.split(".")
    return date(int(y), int(m), int(d))


def _iso(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower())
    return "".join(c for c in s if c.isalnum())


def month_floor(d: date) -> date:
    return date(d.year, d.month, 1)


def build(x: Any, cfg: dict, sw: Switches, reviewer: Reviewer | None, horizon_start: date, horizon_end: date) -> Model:
    """x: the systems' exports (old HRIS, new HRIS, payroll, ATS)."""
    hris = cfg["hris"]
    cut = date.fromisoformat(hris["cutover"])
    depts = dict(cfg["org"]["old_departments"])
    if not sw.rename_map:  # a map made once, before the rename
        depts = {k: v for k, v in depts.items() if k != "KI & Autonomie"}
    issues: list[Issue] = []
    corrections: dict[str, int] = {}
    minutes = 0.0
    review_min = float(cfg["quality"]["review_minutes"])

    def bump(rule: str, n: int = 1) -> None:
        corrections[rule] = corrections.get(rule, 0) + n

    # ---- adapters ---------------------------------------------------------------------------------------------
    old = {}
    for r in x.old_workers:
        kind = hris["old_kinds"][r["beschaeftigungsart"]]
        if sw.quality and r["kostenstelle"].endswith("-EXT") and kind != "contractor":
            kind = "contractor"
            bump("contractor_recorded_as_employee")
        old[str(r["personal_nr"])] = {
            "first": r["vorname"],
            "last": r["nachname"],
            "dob": _de(r["geburtsdatum"]),
            "hire": _de(r["eintrittsdatum"]),
            "exit": _de(r["austrittsdatum"]),
            "exit_kind": hris["old_exits"].get(r["austrittsgrund"]) or None,
            "kind": kind,
            "fte": (float(r["wochenstunden"]) / 40) if r["wochenstunden"] != "" else 1.0,
            "country": r["land"],
            "regrettable": None,
        }
    old_org: dict[str, list[tuple[date, str]]] = {}
    unknown_names: dict[str, str] = {}
    learned: dict[str, str] = {}
    for r in x.old_departments:
        name = r["abteilung"]
        team = depts.get(name)
        if team is None:
            if sw.quality and reviewer is not None:
                if name not in unknown_names:
                    unknown_names[name] = reviewer.team_for(name)
                    issues.append(Issue("unknown_department", "", name, unknown_names[name]))
                    minutes += review_min
                    learned[unknown_names[name]] = reviewer.department_of(unknown_names[name])
                team = unknown_names[name]
            else:
                team = "UNMAPPED"
        old_org.setdefault(str(r["personal_nr"]), []).append((_de(r["gueltig_ab"]), team))  # type: ignore[arg-type]
    old_comp: dict[str, list[tuple[date, float, int]]] = {}
    for r in x.old_salaries:
        when = _de(r["gueltig_ab"])
        assert when is not None
        old_comp.setdefault(str(r["personal_nr"]), []).append((when, float(r["jahresgehalt"]), int(r["stufe"])))
    old_leave: dict[str, list[tuple[date, date]]] = {}
    for r in x.old_leaves:
        old_leave.setdefault(str(r["personal_nr"]), []).append((_de(r["von"]), _de(r["bis"])))  # type: ignore[arg-type]

    new = {}
    for r in x.new_workers:
        kind = hris["new_kinds"][r["employment_type"]] if r["worker_type"] == "Employee" else "contractor"
        new[r["worker_id"]] = {
            "first": r["legal_first_name"],
            "last": r["legal_last_name"],
            "dob": _iso(r["date_of_birth"]),
            "hire": _iso(r["hire_date"]),
            "exit": _iso(r["termination_date"]),
            "exit_kind": hris["new_exits"].get(r["termination_category"]) or None,
            "kind": kind,
            "fte": float(r["fte"]),
            "country": r["country"],
            "regrettable": {"Yes": True, "No": False}.get(r["regrettable"]),
        }
    known_codes = set(cfg["org"]["teams"])
    new_org: dict[str, list[tuple[date, str]]] = {}
    for r in x.new_org:
        code = r["org_unit"]
        if code not in known_codes:
            if sw.quality and reviewer is not None:
                if code not in unknown_names:
                    unknown_names[code] = reviewer.team_for(code)
                    issues.append(Issue("unknown_org_unit", "", code, unknown_names[code]))
                    minutes += review_min
                    learned[unknown_names[code]] = reviewer.department_of(unknown_names[code])
                code = unknown_names[code]
            else:
                code = "UNMAPPED"
        new_org.setdefault(r["worker_id"], []).append((_iso(r["effective_date"]), code))  # type: ignore[arg-type]
    new_comp: dict[str, list[tuple[date, float, int]]] = {}
    for r in x.new_comp:
        eff = _iso(r["effective_date"])
        assert eff is not None
        new_comp.setdefault(r["worker_id"], []).append((eff, float(r["annual_base"]), int(r["job_level"])))
    new_leave: dict[str, list[tuple[date, date]]] = {}
    for r in x.new_leaves:
        new_leave.setdefault(r["worker_id"], []).append((_iso(r["start"]), _iso(r["end"])))  # type: ignore[arg-type]
    paid: dict[str, set[date]] = {}
    for r in x.payroll:
        y, m = r["month"].split("-")
        paid.setdefault(r["payroll_id"], set()).add(date(int(y), int(m), 1))

    # ---- identity: one worker per employment, across both systems ---------------------------------------------
    workers: dict[str, dict] = {}
    links: dict[str, list[tuple[str, str]]] = {}  # worker key -> [(source, id)]
    by_person: dict[tuple[str, str, date], list[str]] = {}
    for nr, o in old.items():
        by_person.setdefault((norm(o["first"]), norm(o["last"]), o["dob"]), []).append(nr)
    matched_old: set[str] = set()
    for wid, n in new.items():
        rec = dict(n)
        key = wid
        sources = [("new", wid)]
        candidates = by_person.get((norm(n["first"]), norm(n["last"]), n["dob"]), []) if sw.identity else []
        candidates = [
            c for c in candidates if c not in matched_old and (old[c]["exit"] is None or old[c]["exit"] >= cut)
        ]
        if candidates:
            # a rehire has two old records; pair on the hire date, else in migration order (oldest first)
            same = [c for c in candidates if old[c]["hire"] == n["hire"]]
            nr = same[0] if same else min(candidates, key=lambda c: (old[c]["hire"], int(c)))
            matched_old.add(nr)
            o = old[nr]
            key = f"{nr}|{wid}"
            sources = [("old", nr), ("new", wid)]
            if sw.quality and o["kind"] == "contractor" and rec["kind"] != "contractor":
                rec["kind"] = "contractor"
                bump("contractor_recorded_as_employee")
            if sw.quality and rec["hire"] == cut and o["hire"] < cut:
                rec["hire"] = o["hire"]
                bump("tenure_reset_at_migration")
            rec["visible_from"] = None
        else:
            rec["visible_from"] = cut if not sw.identity else None
        rec["visible_to"] = None
        workers[key] = rec
        links[key] = sources
    for nr, o in old.items():
        if nr in matched_old:
            continue
        rec = dict(o)
        rec["visible_from"] = None
        # without identity the old record stops at go-live; the new HRIS takes over from there
        rec["visible_to"] = cut - timedelta(days=1) if not sw.identity else None
        workers[nr] = rec
        links[nr] = [("old", nr)]

    def history(key: str, old_rows: dict, new_rows: dict) -> list:
        rows: list = []
        for s, i in links[key]:
            src = old_rows if s == "old" else new_rows
            part = [r for r in src.get(i, [])]
            if s == "old" and len(links[key]) > 1:
                part = [r for r in part if r[0] < cut]
            rows += part
        return sorted(rows, key=lambda r: r[0])

    # ---- quality: the HRIS against payroll ----------------------------------------------------------------------
    gap = int(cfg["quality"]["payroll_gap_months"])
    last_month = month_floor(horizon_end)
    if sw.quality and reviewer is not None:
        for key, w in workers.items():
            if w["kind"] == "contractor" or w["hire"] is None:
                continue
            months_paid: set[date] = set()
            for _src, i in links[key]:
                months_paid |= paid.get(i, set())
            leaves = history(key, old_leave, new_leave)

            def on_leave(m: date, leaves: list = leaves) -> bool:
                me = (m.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                return any(a <= m and b >= me for a, b in leaves)

            # paid after the recorded last day: the exit date is wrong
            if w["exit"] is not None and any(pm > month_floor(w["exit"]) for pm in months_paid):
                src, sid = links[key][-1]
                truth = reviewer.exit_of(src, sid)
                minutes += review_min
                if truth:
                    issues.append(Issue("paid_after_exit", key, f"recorded {w['exit']}", f"last day {truth['exit']}"))
                    w["exit"], w["exit_kind"] = truth["exit"], truth["exit_kind"]
                    bump("paid_after_exit")
            # active on paper, unpaid for months, no leave on record: left, or on leave nobody recorded
            m = max(month_floor(w["hire"]), month_floor(horizon_start))
            stop = month_floor(w["exit"]) if w["exit"] else last_month
            run: list[date] = []
            while m <= stop:
                if m not in months_paid and not on_leave(m) and m != month_floor(w["hire"]):
                    run.append(m)
                else:
                    run = []
                if len(run) >= gap and m <= last_month:
                    src, sid = links[key][-1] if run[0] >= cut else links[key][0]
                    minutes += review_min
                    truth = reviewer.exit_of(src, sid)
                    lv = reviewer.leave_of(src, sid, run[0])
                    if lv is not None:
                        leaves.append(lv)
                        (new_leave if src == "new" else old_leave).setdefault(sid, []).append(lv)
                        issues.append(Issue("unpaid_on_unrecorded_leave", key, f"from {run[0]}", f"leave {lv[0]}"))
                        bump("leave_not_recorded")
                        run = []
                    elif truth and (w["exit"] is None or truth["exit"] < w["exit"]):
                        issues.append(Issue("unpaid_but_active", key, f"from {run[0]}", f"left {truth['exit']}"))
                        w["exit"], w["exit_kind"] = truth["exit"], truth["exit_kind"]
                        bump("exit_never_recorded")
                        break
                    else:
                        run = []
                m = (m + timedelta(days=32)).replace(day=1)

    # ---- frames -------------------------------------------------------------------------------------------------
    wrows, orows, crows, lrows = [], [], [], []
    for key, w in workers.items():
        wrows.append(
            {
                "worker_key": key,
                **{
                    k: w[k]
                    for k in (
                        "kind",
                        "country",
                        "hire",
                        "exit",
                        "exit_kind",
                        "regrettable",
                        "fte",
                        "visible_from",
                        "visible_to",
                    )
                },
            }
        )
        for when, team in history(key, old_org, new_org):
            orows.append({"worker_key": key, "valid_from": when, "team": team})
        for when, sal, lv in history(key, old_comp, new_comp):
            crows.append({"worker_key": key, "valid_from": when, "salary": sal, "level": lv})
        for a, b in history(key, old_leave, new_leave):
            lrows.append({"worker_key": key, "start": a, "end": b})

    reqs = []
    zd, zi = int(cfg["quality"]["zombie_req_days"]), int(cfg["quality"]["zombie_idle_days"])
    for r in x.requisitions:
        opened, closed, act = _iso(r["opened_at"]), _iso(r["closed_at"]), _iso(r["last_activity_at"])
        status = r["status"]
        if (
            sw.quality
            and status == "open"
            and opened
            and act
            and (horizon_end - opened).days >= zd
            and (horizon_end - act).days >= zi
        ):
            status, closed = "closed", act
            bump("zombie_requisition_closed")
        reqs.append(
            {
                "req_id": r["req_id"],
                "team": r["org_unit"] if r["org_unit"] in known_codes | set(learned) else "UNMAPPED",
                "family": r["job_family"],
                "opened": opened,
                "status": status,
                "closed": closed,
                "offers": int(r["offers"]),
            }
        )
    return Model(
        pd.DataFrame(wrows),
        pd.DataFrame(orows),
        pd.DataFrame(crows),
        pd.DataFrame(lrows, columns=["worker_key", "start", "end"]),
        pd.DataFrame(reqs),
        issues,
        corrections,
        minutes,
        learned,
    )
