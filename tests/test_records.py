"""Adapters, identity and checks: what each one is for, on the real exports."""

from paf.platform import records
from paf.world.truth import PeopleTeam


def build(W, cfg, **sw):  # type: ignore[no-untyped-def]
    s = records.Switches(**sw)
    return records.build(
        W.exports, cfg, s, PeopleTeam(W.company, W.keys) if s.quality else None, W.company.start, W.end
    )


def eid_of(W, key: str) -> int:  # type: ignore[no-untyped-def]
    inv = {str(v): e for e, v in W.keys.old_nr.items()} | {v: e for e, v in W.keys.new_id.items()}
    return inv[key.split("|")[-1]]


def test_every_linked_worker_is_one_real_employment(W, cfg) -> None:  # type: ignore[no-untyped-def]
    m = build(W, cfg)
    inv_old = {str(v): e for e, v in W.keys.old_nr.items()}
    inv_new = {v: e for e, v in W.keys.new_id.items()}
    linked = [k for k in m.workers["worker_key"] if "|" in k]
    assert linked
    for k in linked:
        o, n = k.split("|")
        assert inv_old[o] == inv_new[n]


def test_checks_restore_hire_dates_and_exits(W, cfg) -> None:  # type: ignore[no-untyped-def]
    m = build(W, cfg)
    assert m.corrections["tenure_reset_at_migration"] > 50
    for r in m.workers.itertuples(index=False):
        e = W.company.jobs[eid_of(W, r.worker_key)]
        assert r.hire == e.hire
        if e.kind != "contractor":
            truth_exit = e.exit if e.exit and e.exit <= W.end else None
            recorded = r.exit if (r.exit == r.exit and r.exit is not None and r.exit <= W.end) else None
            assert recorded == truth_exit, r.worker_key  # a termination already scheduled after the horizon is fine


def test_contractors_on_external_cost_centres_are_not_employees(W, cfg) -> None:  # type: ignore[no-untyped-def]
    m = build(W, cfg)
    for r in m.workers.itertuples(index=False):
        assert (r.kind == "contractor") == (W.company.jobs[eid_of(W, r.worker_key)].kind == "contractor")


def test_unknown_departments_are_asked_about_never_guessed(W, cfg) -> None:  # type: ignore[no-untyped-def]
    no_rename = {
        **cfg,
        "org": {
            **cfg["org"],
            "old_departments": {k: v for k, v in cfg["org"]["old_departments"].items() if k != "KI & Autonomie"},
        },
    }
    blind = build(W, no_rename, quality=False)
    assert (blind.org["team"] == "UNMAPPED").any()
    asked = build(W, no_rename)
    assert any(i.rule == "unknown_department" and i.resolved == "ENG-AUT" for i in asked.issues)
    assert not (asked.org["team"] == "UNMAPPED").any()


def test_without_identity_old_records_stop_at_go_live(W, cfg) -> None:  # type: ignore[no-untyped-def]
    m = build(W, cfg, identity=False, quality=False)
    assert not any("|" in k for k in m.workers["worker_key"])
    old = m.workers[m.workers["worker_key"].str.isdigit()]
    assert old["visible_to"].notna().all()
