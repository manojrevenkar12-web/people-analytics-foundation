"""The held-out seeds run once; generated files agree with the catalogue."""

import json

import pytest
import yaml

from paf.lab import study


def test_a_second_held_out_run_is_refused(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(study, "REPORTS", tmp_path)
    monkeypatch.setattr(study, "LOCK", tmp_path / "heldout.lock")
    (tmp_path / "heldout.lock").write_text('{"seeds": [201, 202]}\n')
    with pytest.raises(SystemExit) as e:
        study.run_heldout()
    assert e.value.code == 3


def test_the_lock_matches_the_report() -> None:
    if not study.LOCK.exists():
        pytest.skip("held-out seeds have not run")
    assert (
        json.loads(study.LOCK.read_text())["seeds"] == json.loads((study.REPORTS / "heldout.json").read_text())["seeds"]
    )


def test_every_catalogue_kpi_has_a_dax_measure_and_nothing_else() -> None:
    root = study.ROOT
    if not (root / "bi" / "measures.dax").exists():
        pytest.skip("report not generated")
    catalogue = yaml.safe_load((root / "config" / "kpis.yml").read_text())
    dax = (root / "bi" / "measures.dax").read_text()
    for k in catalogue:
        assert f'dim_kpi[kpi_id] = "{k["id"]}"' in dax
    assert dax.count("CALCULATE") == len(catalogue)
