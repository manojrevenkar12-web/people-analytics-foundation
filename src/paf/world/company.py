"""The company as it really is, month by month: who joins, who moves, who leaves and why, how long hiring takes.

Everything here is truth. The platform only ever sees what the HR systems record about it (`world/systems.py`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from paf.world import luck

FIRST = [
    "Anna",
    "Ben",
    "Clara",
    "David",
    "Elif",
    "Felix",
    "Greta",
    "Hannah",
    "Ivan",
    "Jonas",
    "Karin",
    "Lukas",
    "Mara",
    "Nils",
    "Olga",
    "Paul",
    "Rosa",
    "Sami",
    "Tobias",
    "Vera",
    "Yara",
    "Zoe",
    "Amir",
    "Bea",
    "Chen",
    "Dario",
    "Emma",
    "Farid",
    "Gina",
    "Hugo",
    "Ines",
    "Jan",
    "Kemal",
    "Lea",
    "Milan",
    "Nora",
    "Omar",
    "Priya",
    "Oleksii",
    "Iryna",
    "Taras",
    "Kateryna",
    "Liam",
    "Olivia",
    "Noah",
    "Amelia",
    "Jakub",
    "Zofia",
    "Maximilian",
    "Sophie",
]
LAST = [
    "Müller",
    "Schmidt",
    "Schneider",
    "Fischer",
    "Weber",
    "Meyer",
    "Wagner",
    "Becker",
    "Schulz",
    "Hoffmann",
    "Koch",
    "Richter",
    "Klein",
    "Wolf",
    "Neumann",
    "Schwarz",
    "Zimmermann",
    "Braun",
    "Krüger",
    "Hartmann",
    "Shevchenko",
    "Kovalenko",
    "Bondarenko",
    "Tkachenko",
    "Smith",
    "Jones",
    "Taylor",
    "Brown",
    "Nowak",
    "Kowalski",
    "Yilmaz",
    "Demir",
    "Rossi",
    "Dubois",
    "Novak",
    "Horvat",
    "Lehmann",
    "Krause",
    "Maier",
    "Köhler",
]

LEVEL_MID = {1: 50_000, 2: 62_000, 3: 77_000, 4: 95_000, 5: 118_000}
COUNTRY_FACTOR = {"DE": 1.0, "UK": 1.05, "UA": 0.45, "PL": 0.55}
OTHER_REASONS = ["career_growth", "relocation", "role_fit", "culture"]


def month_start(start: date, m: int) -> date:
    y, mo = start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1
    return date(y, mo, 1)


def month_end(start: date, m: int) -> date:
    return month_start(start, m + 1) - timedelta(days=1)


def month_of(start: date, d: date) -> int:
    return (d.year - start.year) * 12 + d.month - start.month


@dataclass
class Person:
    pid: int
    first: str
    last: str
    dob: date


@dataclass
class Employment:
    eid: int
    pid: int
    team: str
    country: str
    family: str
    level: int
    kind: str  # permanent | fixed_term | student | contractor
    fte: float
    hire: date
    perf: str  # high | mid | low
    salary_history: list[tuple[date, float]] = field(default_factory=list)
    team_history: list[tuple[date, str]] = field(default_factory=list)
    level_history: list[tuple[date, int]] = field(default_factory=list)
    last_promotion: date | None = None
    notice: date | None = None
    exit: date | None = None  # last day
    exit_kind: str | None = None  # voluntary | involuntary | contract_end
    regrettable: bool = False
    reason: str | None = None
    contract_end: date | None = None
    leaves: list[tuple[date, date]] = field(default_factory=list)  # parental leave, inclusive
    rehire: bool = False
    req: int | None = None

    def active_on(self, d: date) -> bool:
        return self.hire <= d and (self.exit is None or self.exit >= d)

    def team_on(self, d: date) -> str:
        t = self.team_history[0][1]
        for when, code in self.team_history:
            if when <= d:
                t = code
        return t

    def salary_on(self, d: date) -> float:
        s = self.salary_history[0][1]
        for when, v in self.salary_history:
            if when <= d:
                s = v
        return s

    def level_on(self, d: date) -> int:
        lv = self.level_history[0][1]
        for when, v in self.level_history:
            if when <= d:
                lv = v
        return lv

    def on_leave(self, d: date) -> bool:
        return any(a <= d <= b for a, b in self.leaves)


@dataclass
class Requisition:
    rid: int
    team: str
    family: str
    opened: date
    clearance: bool
    filled: date | None = None
    cancelled: date | None = None
    applicants: int = 0
    offers: int = 0
    eid: int | None = None


@dataclass
class Company:
    start: date
    months: int
    cutover: int
    teams: list[dict]
    persons: dict[int, Person]
    jobs: dict[int, Employment]
    reqs: dict[int, Requisition]
    managers: dict[str, list[tuple[date, bool]]]  # team -> (from, weak?)
    absence_days: dict[tuple[int, int], int]  # (eid, month) -> sick days

    def team(self, code: str) -> dict:
        return next(t for t in self.teams if t["code"] == code)

    def weak_manager(self, team: str, d: date) -> bool:
        weak = False
        for when, w in self.managers[team]:
            if when <= d:
                weak = w
        return weak

    def manager_changed_within(self, team: str, d: date, days: int) -> bool:
        return any(d - timedelta(days=days) < when <= d for when, _ in self.managers[team][1:])


def band_mid(level: int, country: str) -> float:
    return LEVEL_MID[level] * COUNTRY_FACTOR[country]


def _day_in(seed: int, start: date, m: int, *key: object) -> date:
    a, b = month_start(start, m), month_end(start, m)
    return a + timedelta(days=int(luck.uniform(seed, *key) * ((b - a).days + 1)))


def simulate(seed: int, w: dict, world_name: str) -> Company:
    c = w["company"]
    h = w["hiring"]
    variant = w[world_name]
    start = date.fromisoformat(c["start"] + "-01")
    months = int(c["months"])
    growth_scale = float(variant.get("growth_scale", 1.0))
    teams = [dict(t) for t in c["teams"]]
    if "extra_team" in variant:
        teams.append(dict(variant["extra_team"]))
    drivers = c["drivers"]

    persons: dict[int, Person] = {}
    jobs: dict[int, Employment] = {}
    reqs: dict[int, Requisition] = {}
    managers: dict[str, list[tuple[date, bool]]] = {
        t["code"]: [(start - timedelta(days=400), luck.uniform(seed, "mgr", t["code"], 0) < c["weak_manager_share"])]
        for t in teams
    }
    absence: dict[tuple[int, int], int] = {}
    leavers_for_rehire: list[int] = []

    def new_person() -> Person:
        pid = len(persons) + 1
        p = Person(
            pid,
            luck.choice(seed, FIRST, "first", pid),
            luck.choice(seed, LAST, "last", pid),
            date(1965, 1, 1) + timedelta(days=int(luck.uniform(seed, "dob", pid) * 365 * 37)),
        )
        persons[pid] = p
        return p

    def hire(team: dict, when: date, req: int | None) -> Employment:
        eid = len(jobs) + 1
        pid = None
        if leavers_for_rehire and luck.uniform(seed, "rehire", eid) < c["rehire_share"]:
            pid = leavers_for_rehire.pop(int(luck.uniform(seed, "rehirewho", eid) * len(leavers_for_rehire)))
        if pid is None:
            pid = new_person().pid
        u = luck.uniform(seed, "kind", eid)
        kind = (
            "contractor"
            if u < c["contractor_share"]
            else "fixed_term"
            if u < c["contractor_share"] + c["fixed_term_share"]
            else "student"
            if u < c["contractor_share"] + c["fixed_term_share"] + c["student_share"]
            else "permanent"
        )
        level = 1 + int(luck.uniform(seed, "level", eid) * 4) if kind != "student" else 1
        under = luck.uniform(seed, "under", eid) < c["underpaid_share"]
        compa = (
            (0.78 + 0.11 * luck.uniform(seed, "compa", eid))
            if under
            else (0.92 + 0.2 * luck.uniform(seed, "compa", eid))
        )
        perf_u = luck.uniform(seed, "perf", eid)
        perf = "high" if perf_u < c["high_performer_share"] else "low" if perf_u > 0.85 else "mid"
        fte = 0.5 if kind == "student" else (0.8 if luck.uniform(seed, "pt", eid) < 0.1 else 1.0)
        e = Employment(
            eid,
            pid,
            team["code"],
            team["country"],
            team["family"],
            level,
            kind,
            fte,
            when,
            perf,
            salary_history=[(when, round(band_mid(level, team["country"]) * compa, -2))],
            team_history=[(when, team["code"])],
            level_history=[(when, level)],
            last_promotion=when,
            rehire=pid in {j.pid for j in jobs.values()},
            req=req,
        )
        if kind == "fixed_term":
            e.contract_end = when + timedelta(days=int(365 + luck.uniform(seed, "fterm", eid) * 365))
        jobs[eid] = e
        return e

    # the founding team, hired over the two years before the start
    for t in teams:
        n = int(t["start"])
        for i in range(n):
            back = int(luck.uniform(seed, "seedhire", t["code"], i) * 730) + 1
            hire(t, start - timedelta(days=back), None)

    def open_req(t: dict, when: date) -> None:
        rid = len(reqs) + 1
        fam = h["families"][t["family"]]
        clear = luck.uniform(seed, "clear", rid) < fam["clearance_share"]
        z = luck.normal(seed, "ttf", rid)
        days = fam["median_days"] * math.exp(fam["sigma"] * z) + (h["clearance_days"] if clear else 0)
        offers = 1
        while luck.uniform(seed, "decline", rid, offers) < fam["decline"] and offers < 4:
            offers += 1
            days += 18
        r = Requisition(rid, t["code"], t["family"], when, clear, offers=offers)
        lo, hi = h["applicants_per_req"]
        r.applicants = luck.randint(seed, lo, hi, "apps", rid)
        if luck.uniform(seed, "cancel", rid) < h["cancel_share"]:
            r.cancelled = when + timedelta(days=30 + int(luck.uniform(seed, "canceldays", rid) * 90))
        else:
            r.filled = when + timedelta(days=int(days))
        reqs[rid] = r

    for m in range(months):
        ms, me = month_start(start, m), month_end(start, m)
        # managers change now and then
        for t in teams:
            if luck.uniform(seed, "mgrchange", t["code"], m) < 0.025:
                managers[t["code"]].append((ms, luck.uniform(seed, "mgr", t["code"], m + 1) < c["weak_manager_share"]))
        # requisitions that start this month become hires
        for r in reqs.values():
            if r.filled and ms <= r.filled <= me and r.eid is None:
                r.eid = hire(next(t for t in teams if t["code"] == r.team), r.filled, r.rid).eid
        active = [e for e in jobs.values() if e.active_on(ms)]
        for e in active:
            if e.notice is not None:
                continue
            # absences and leave
            absence[(e.eid, m)] = (
                0
                if e.kind == "contractor"
                else int(-c["absence_days_mean"] * math.log(max(1e-9, 1 - luck.uniform(seed, "abs", e.eid, m))))
            )
            if (
                e.kind in ("permanent", "fixed_term")
                and not e.on_leave(ms)
                and luck.uniform(seed, "leave", e.eid, m) < c["parental_leave_monthly"]
            ):
                a = _day_in(seed, start, m, "leaveday", e.eid)
                e.leaves.append((a, a + timedelta(days=int(90 + luck.uniform(seed, "leavelen", e.eid) * 270))))
            # yearly pay review in April; promotions for high performers
            if ms.month == 4 and e.hire < ms - timedelta(days=90):
                cur = e.salary_on(ms)
                lv = e.level_on(ms)
                fix = cur < 0.9 * band_mid(lv, e.country) and luck.uniform(seed, "fixpay", e.eid, m) < 0.3
                new = (
                    band_mid(lv, e.country) * 0.96
                    if fix
                    else cur * (1.02 + 0.03 * luck.uniform(seed, "raise", e.eid, m))
                )
                e.salary_history.append((ms, round(new, -2)))
            if e.perf == "high" and e.kind == "permanent" and luck.uniform(seed, "promo", e.eid, m) < 1 / 26:
                lv = min(5, e.level_on(ms) + 1)
                e.level_history.append((ms, lv))
                e.salary_history.append((ms, round(e.salary_on(ms) * 1.1, -2)))
                e.last_promotion = ms
            if luck.uniform(seed, "transfer", e.eid, m) < 0.004:
                same = [t for t in teams if t["dept"] == next(x for x in teams if x["code"] == e.team_on(ms))["dept"]]
                dest = luck.choice(seed, same, "dest", e.eid, m)
                if dest["code"] != e.team_on(ms) and dest["country"] == e.country:
                    e.team_history.append((ms, dest["code"]))
            # contract ends
            if e.contract_end and e.contract_end <= me:
                if luck.uniform(seed, "convert", e.eid) < 0.5:
                    e.kind = "permanent"
                    e.contract_end = None
                else:
                    e.notice, e.exit, e.exit_kind, e.reason = (
                        e.contract_end - timedelta(days=30),
                        e.contract_end,
                        "contract_end",
                        "contract_end",
                    )
                    continue
            if e.kind == "contractor":
                if luck.uniform(seed, "cexit", e.eid, m) < 0.03:
                    e.notice = e.exit = _day_in(seed, start, m, "cday", e.eid)
                    e.exit_kind, e.reason = "contract_end", "contract_end"
                continue
            # voluntary exits: base hazard times what is true for this person this month
            team = next(t for t in teams if t["code"] == e.team_on(ms))
            mult: dict[str, float] = {}
            if e.salary_on(ms) < 0.9 * band_mid(e.level_on(ms), e.country):
                mult["pay"] = drivers["underpaid"]
            if _weak(managers, team["code"], ms):
                mult["manager"] = drivers["weak_manager"]
            if (ms - e.hire).days < 182:
                mult["role_fit"] = drivers["new_starter"]
            if team.get("overtime") and ms.month >= 9:
                mult["workload"] = drivers["overtime_season"]
            if e.perf == "high" and e.last_promotion and (ms - e.last_promotion).days > 900:
                mult["career_growth"] = drivers["passed_over"]
            if _mgr_changed(managers, team["code"], ms, 182):
                mult["manager"] = mult.get("manager", 1.0) * drivers["manager_change"]
            hazard = float(team["hazard"])
            for v in mult.values():
                hazard *= v
            if luck.uniform(seed, "vol", e.eid, m) < hazard:
                e.notice = _day_in(seed, start, m, "notice", e.eid)
                lo, hi = c["notice_months"]
                e.exit = e.notice + timedelta(days=30 * luck.randint(seed, lo, hi, "noticelen", e.eid))
                e.exit_kind = "voluntary"
                e.regrettable = e.perf == "high" or (e.perf == "mid" and luck.uniform(seed, "regret", e.eid) < 0.4)
                if mult:
                    weights = {k: v - 1 for k, v in mult.items()}
                    u = luck.uniform(seed, "why", e.eid) * sum(weights.values())
                    for k, v in weights.items():
                        u -= v
                        if u <= 0:
                            e.reason = k
                            break
                    e.reason = e.reason or next(iter(weights))
                else:
                    e.reason = luck.choice(seed, OTHER_REASONS, "other", e.eid)
                leavers_for_rehire.append(e.pid)
                continue
            if luck.uniform(seed, "invol", e.eid, m) < c["involuntary_monthly"] * (2.0 if e.perf == "low" else 1.0):
                e.notice = _day_in(seed, start, m, "inotice", e.eid)
                e.exit = e.notice + timedelta(days=30)
                e.exit_kind, e.reason = "involuntary", "involuntary"
        # hiring to plan: replace leavers and grow
        for t in teams:
            if t.get("opens_month") is not None and m < int(t["opens_month"]):
                continue
            if t.get("opens_month") is not None and m == int(t["opens_month"]):
                for i in range(int(t["opens_with"])):
                    hire(t, ms + timedelta(days=i % 20), None)
                continue
            base = float(t["start"]) if t.get("opens_month") is None else float(t["opens_with"])
            months_in = m if t.get("opens_month") is None else m - int(t["opens_month"])
            target = round(base * (1 + float(t["growth"]) * growth_scale) ** months_in)
            here = sum(1 for e in jobs.values() if e.team_on(me) == t["code"] and e.active_on(me) and e.notice is None)
            pending = sum(
                1
                for r in reqs.values()
                if r.team == t["code"]
                and r.eid is None
                and ((r.filled and r.filled > me) or (r.cancelled and r.cancelled > me))
            )
            for i in range(max(0, target - here - pending)):
                open_req(t, _day_in(seed, start, m, "reqday", t["code"], i))
    return Company(start, months, int(w["company"]["cutover_month"]), teams, persons, jobs, reqs, managers, absence)


def _weak(managers: dict[str, list[tuple[date, bool]]], team: str, d: date) -> bool:
    weak = False
    for when, wk in managers[team]:
        if when <= d:
            weak = wk
    return weak


def _mgr_changed(managers: dict[str, list[tuple[date, bool]]], team: str, d: date, days: int) -> bool:
    return any(d - timedelta(days=days) < when <= d for when, _ in managers[team][1:])
