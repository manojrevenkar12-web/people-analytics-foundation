# Repeatable tasks

## Add a KPI
1. Add it to `config/kpis.yml` (id, name, owner, definition, value, population, unit).
2. If it needs a new additive component, count it per team and month in `COMPONENTS_SQL` (`platform/kpis.py`) and
   add it to `kpi_cells`; never average a ratio up the tree.
3. Give it a tolerance in `lab/simulate.py::TOL`, run the study and `python -m paf.cli report` (the DAX measure and
   the console catalogue follow).

## Add a data check
1. Write it in `platform/records.py`. If code can settle it from the systems, settle it; if not, ask the reviewer
   and count the minutes.
2. Make the world produce the mistake at a rate in `world.yml` (`world/systems.py`).
3. Add a test in `tests/test_records.py` and an ablation if it matters.

## Map a new department or org unit
Add the old-HRIS name or the new code to `config/platform.yml: org`. Until then the adapter asks the People team.

## Add a policy passage to the assistant
Add the passage and its topic words to `config/platform.yml: helpdesk`. Add the question to `world/texts.py` so the
study measures it.

## Connect a real model
`ClaudeReader` or `OpenAICompatibleReader` in `platform/readers.py` implement the reader the pilots use. Keys come
from the environment; prompts carry the question or comment only.

## Run the held-out seeds
Once: `python -m paf.cli run heldout`, `python -m paf.cli report`, commit the lock, the report and the generated
files together, and write the ADR with what came out.
