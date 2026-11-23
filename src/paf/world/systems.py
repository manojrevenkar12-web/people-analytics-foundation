"""What the company's systems record: the old HRIS, the new HRIS after the migration, payroll, the ATS, the exit
survey and the People helpdesk. Mistakes included, at the rates in world.yml. The platform reads these exports and
nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from paf.world import luck
from paf.world.company import Company, Employment, month_end, month_of, month_start

KIND_DE = {
    "permanent": "Festanstellung",
    "fixed_term": "Befristet",
    "student": "Werkstudent",
    "contractor": "Freelancer",
}
EXIT_DE = {"voluntary": "Eigenkündigung", "involuntary": "Arbeitgeberkündigung", "contract_end": "Befristung"}
KIND_NEW = {
    "permanent": "Permanent",
    "fixed_term": "Fixed Term",
    "student": "Working Student",
    "contractor": "Contract",
}
EXIT_NEW = {"voluntary": "Voluntary", "involuntary": "Involuntary", "contract_end": "End of Contract"}


@dataclass
class Exports:
    old_workers: list[dict] = field(default_factory=list)
    old_departments: list[dict] = field(default_factory=list)
    old_salaries: list[dict] = field(default_factory=list)
    old_leaves: list[dict] = field(default_factory=list)
    new_workers: list[dict] = field(default_factory=list)
    new_org: list[dict] = field(default_factory=list)
    new_comp: list[dict] = field(default_factory=list)
    new_leaves: list[dict] = field(default_factory=list)
    payroll: list[dict] = field(default_factory=list)
    requisitions: list[dict] = field(default_factory=list)
    exit_survey: list[dict] = field(default_factory=list)
    tickets: list[dict] = field(default_factory=list)


@dataclass
class Keys:
    """Which record belongs to which real employment. Truth: only the lab may read it."""

    old_nr: dict[int, int] = field(default_factory=dict)  # eid -> Personal-Nr
    new_id: dict[int, str] = field(default_factory=dict)  # eid -> worker id
    ticket_truth: dict[str, dict] = field(default_factory=dict)
    survey_truth: dict[str, str] = field(default_factory=dict)  # response id -> real reason


def _de(d: date | None) -> str:
    return "" if d is None else d.strftime("%d.%m.%Y")


def _old_dept(company: Company, team: str, d: date) -> str:
    t = company.team(team)
    if t.get("renamed_month") is not None and month_of(company.start, d) >= int(t["renamed_month"]):
        return str(t["renamed_to"])
    return str(t["old"])


def record(company: Company, w: dict, world_name: str, seed: int) -> tuple[Exports, Keys]:
    sysw = w["systems"]
    scale = float(w[world_name].get("error_scale", 1.0))

    def err(system: str, name: str, *key: object) -> bool:
        return luck.uniform(seed, "err", system, name, *key) < float(sysw[system][name]) * scale

    x, k = Exports(), Keys()
    cut = month_start(company.start, company.cutover)
    last = month_end(company.start, company.months - 1)
    jobs = sorted(company.jobs.values(), key=lambda e: (e.hire, e.eid))

    # ---- old HRIS: everyone hired before go-live, as recorded up to the day before go-live ---------------------
    nr = 1000
    for e in jobs:
        if e.hire >= cut:
            continue
        nr += 1
        k.old_nr[e.eid] = nr
        p = company.persons[e.pid]
        kind = e.kind
        if kind == "contractor" and err("old_hris", "contractor_as_employee", e.eid):
            kind = "permanent"
        exit_d = e.exit if e.exit and e.exit < cut else None
        if exit_d is not None and e.exit_kind == "voluntary" and err("old_hris", "notice_as_exit", e.eid):
            exit_d = e.notice
        if exit_d is not None and err("old_hris", "missing_exit", e.eid):
            exit_d = None
        x.old_workers.append(
            {
                "personal_nr": nr,
                "vorname": p.first,
                "nachname": p.last,
                "geburtsdatum": _de(p.dob),
                "eintrittsdatum": _de(e.hire),
                "austrittsdatum": _de(exit_d),
                "austrittsgrund": EXIT_DE[e.exit_kind] if exit_d and e.exit_kind else "",
                "beschaeftigungsart": KIND_DE[kind],
                "wochenstunden": "" if e.kind == "contractor" else round(40 * e.fte),
                "kostenstelle": f"{4000 + 10 * company.teams.index(company.team(e.team))}"
                + ("-EXT" if e.kind == "contractor" else ""),
                "land": e.country,
                "stufe": e.level_history[0][1],
            }
        )
        for when, team in e.team_history:
            if when < cut:
                x.old_departments.append(
                    {"personal_nr": nr, "gueltig_ab": _de(when), "abteilung": _old_dept(company, team, when)}
                )
        # a rename shows up as a new department row on the rename date for people already there
        t0 = company.team(e.team)
        if t0.get("renamed_month") is not None:
            rd = month_start(company.start, int(t0["renamed_month"]))
            if e.hire < rd < cut and e.team_on(rd) == e.team and (e.exit is None or e.exit >= rd):
                x.old_departments.append({"personal_nr": nr, "gueltig_ab": _de(rd), "abteilung": str(t0["renamed_to"])})
        if e.kind != "contractor":
            for when, sal in e.salary_history:
                if when < cut:
                    x.old_salaries.append(
                        {"personal_nr": nr, "gueltig_ab": _de(when), "jahresgehalt": sal, "stufe": e.level_on(when)}
                    )
        for a, b in e.leaves:
            if a < cut and not err("old_hris", "leave_not_recorded", e.eid, a):
                x.old_leaves.append({"personal_nr": nr, "art": "Elternzeit", "von": _de(a), "bis": _de(b)})

    # ---- new HRIS: migrated at go-live (as the old HRIS saw them) plus everyone hired since -------------------
    wid = 0
    old_by_eid = {r["personal_nr"]: r for r in x.old_workers}
    for e in jobs:
        migrated = e.hire < cut
        if migrated:
            rec = old_by_eid[k.old_nr[e.eid]]
            looks_active = rec["austrittsdatum"] == "" or _parse_de(rec["austrittsdatum"]) >= cut
            if not looks_active:
                continue
        elif e.hire > last:
            continue
        wid += 1
        w_id = f"W-{wid:05d}"
        k.new_id[e.eid] = w_id
        p = company.persons[e.pid]
        hire_d = e.hire
        if migrated and err("migration", "tenure_reset", e.eid):
            hire_d = cut
        kind = e.kind
        if migrated and old_by_eid[k.old_nr[e.eid]]["beschaeftigungsart"] != "Freelancer" and e.kind == "contractor":
            kind = "permanent"  # the old mistake travels with the migration
        exit_d = e.exit if e.exit and e.exit >= cut else None
        if migrated and e.exit and e.exit < cut:
            exit_d = None  # a leaver the old HRIS never closed: migrated as active
        if exit_d is not None and err("new_hris", "missing_exit", e.eid):
            exit_d = None
        x.new_workers.append(
            {
                "worker_id": w_id,
                "legal_first_name": p.first,
                "legal_last_name": p.last,
                "date_of_birth": p.dob.isoformat(),
                "hire_date": hire_d.isoformat(),
                "worker_type": "Contingent Worker" if kind == "contractor" else "Employee",
                "employment_type": KIND_NEW[kind],
                "fte": e.fte,
                "country": e.country,
                "termination_date": exit_d.isoformat() if exit_d else "",
                "termination_category": EXIT_NEW[e.exit_kind] if exit_d and e.exit_kind else "",
                "regrettable": ("Yes" if e.regrettable else "No") if exit_d and e.exit_kind == "voluntary" else "",
                "job_level": e.level_on(max(cut, e.hire)),
            }
        )
        start_org = max(cut, e.hire)
        x.new_org.append({"worker_id": w_id, "effective_date": start_org.isoformat(), "org_unit": e.team_on(start_org)})
        for when, team in e.team_history:
            if when > start_org:
                x.new_org.append({"worker_id": w_id, "effective_date": when.isoformat(), "org_unit": team})
        if e.kind != "contractor":
            x.new_comp.append(
                {
                    "worker_id": w_id,
                    "effective_date": start_org.isoformat(),
                    "annual_base": e.salary_on(start_org),
                    "job_level": e.level_on(start_org),
                }
            )
            for when, sal in e.salary_history:
                if when > start_org:
                    x.new_comp.append(
                        {
                            "worker_id": w_id,
                            "effective_date": when.isoformat(),
                            "annual_base": sal,
                            "job_level": e.level_on(when),
                        }
                    )
        for a, b in e.leaves:
            if b >= cut and not err("new_hris", "leave_not_recorded", e.eid, a):
                x.new_leaves.append(
                    {
                        "worker_id": w_id,
                        "leave_type": "Parental",
                        "start": max(a, cut).isoformat(),
                        "end": b.isoformat(),
                    }
                )

    # ---- payroll: who was paid in which month (contractors invoice; parental leave is unpaid) -----------------
    for e in jobs:
        if e.kind == "contractor":
            continue
        for m in range(company.months):
            ms, me = month_start(company.start, m), month_end(company.start, m)
            if not (e.hire <= me and (e.exit is None or e.exit >= ms)):
                continue
            if e.on_leave(ms) and e.on_leave(me):
                continue
            if ms >= cut and e.eid in k.new_id:
                system_id: str | None = k.new_id[e.eid]
            else:
                system_id = str(k.old_nr[e.eid]) if e.eid in k.old_nr else None
            if system_id is None:
                continue
            x.payroll.append(
                {
                    "payroll_id": system_id,
                    "month": ms.strftime("%Y-%m"),
                    "gross": round(e.salary_on(me) / 12 * e.fte, 2),
                }
            )

    # ---- ATS ---------------------------------------------------------------------------------------------------
    for r in company.reqs.values():
        if r.opened > last:
            continue
        status, closed = "open", None
        if r.filled and r.filled <= last:
            status, closed = "filled", r.filled
        elif r.cancelled and r.cancelled <= last:
            status, closed = "closed", r.cancelled
            if err("ats", "zombie_req", r.rid):
                status, closed = "open", None
        last_activity = (closed or min(last, r.cancelled or last)) if r.cancelled else (closed or last)
        x.requisitions.append(
            {
                "req_id": f"REQ-{r.rid:04d}",
                "org_unit": r.team,
                "job_family": r.family,
                "opened_at": r.opened.isoformat(),
                "status": status,
                "closed_at": closed.isoformat() if closed else "",
                "last_activity_at": last_activity.isoformat(),
                "applicants": r.applicants,
                "offers": r.offers,
                "security_clearance": "required" if r.clearance else "",
            }
        )
    return x, k


def _parse_de(s: str) -> date:
    d, m, y = s.split(".")
    return date(int(y), int(m), int(d))


def employment_of(company: Company, eid: int) -> Employment:
    return company.jobs[eid]
