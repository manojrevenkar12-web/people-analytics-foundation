"""The truth stays in the world; the world does not read the platform's settings."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "paf"


def imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
    return out


def test_the_platform_never_imports_the_world_or_the_lab() -> None:
    for f in (SRC / "platform").glob("*.py"):
        assert not any(m.startswith(("paf.world", "paf.lab")) for m in imports(f)), f


def test_the_world_does_not_read_the_platforms_settings() -> None:
    for f in (SRC / "world").glob("*.py"):
        text = f.read_text()
        assert "platform.yml" not in text and "kpis.yml" not in text and "designs.yml" not in text, f
        assert not any(m.startswith("paf.lab") for m in imports(f)), f


def test_only_the_lab_reads_the_answers() -> None:
    for f in SRC.rglob("*.py"):
        if f.parent.name in ("world", "lab"):
            continue
        text = f.read_text()
        for truth in ("survey_truth", "ticket_truth", "true_model", "PeopleTeam"):
            assert truth not in text, (f, truth)
