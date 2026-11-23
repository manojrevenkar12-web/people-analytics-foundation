"""The world: same luck for every design; the systems make the mistakes world.yml says."""

from paf.lab import simulate
from paf.world.company import simulate as sim_company
from paf.world.systems import record

W_CFG = simulate.load("world")


def test_the_same_seed_builds_the_same_company_and_exports() -> None:
    a, b = sim_company(21, W_CFG, "dev"), sim_company(21, W_CFG, "dev")
    assert [(e.hire, e.exit, e.reason) for e in a.jobs.values()] == [
        (e.hire, e.exit, e.reason) for e in b.jobs.values()
    ]
    xa, _ = record(a, W_CFG, "dev", 21)
    xb, _ = record(b, W_CFG, "dev", 21)
    assert xa.old_workers == xb.old_workers and xa.payroll == xb.payroll
    c = sim_company(22, W_CFG, "dev")
    assert [e.hire for e in c.jobs.values()] != [e.hire for e in a.jobs.values()]


def test_the_exports_carry_no_truth(W) -> None:  # type: ignore[no-untyped-def]
    fields = set()
    for rows in (
        W.exports.old_workers,
        W.exports.new_workers,
        W.exports.payroll,
        W.exports.requisitions,
        W.exports.exit_survey,
        W.exports.tickets,
    ):
        for r in rows[:5]:
            fields |= set(r)
    assert not fields & {"reason", "eid", "pid", "perf", "category", "answer", "sensitive", "weak_manager"}


def test_the_migration_resets_hire_dates_and_carries_old_mistakes(W) -> None:  # type: ignore[no-untyped-def]
    cut = "2025-12-01"
    reset = sum(1 for r in W.exports.new_workers if r["hire_date"] == cut)
    migrated = len(W.keys.old_nr.keys() & W.keys.new_id.keys())
    assert 0.15 < reset / migrated < 0.45
    contractors_wrong = [
        r
        for r in W.exports.old_workers
        if r["kostenstelle"].endswith("-EXT") and r["beschaeftigungsart"] != "Freelancer"
    ]
    assert contractors_wrong


def test_the_held_out_world_is_harder() -> None:
    dev = simulate.world("dev", 21)
    ho = simulate.world("heldout", 201)
    assert any(t["code"] == "ENG-PL" for t in ho.company.teams)
    assert not any(t["code"] == "ENG-PL" for t in dev.company.teams)
    assert len(ho.company.jobs) > len(dev.company.jobs)
