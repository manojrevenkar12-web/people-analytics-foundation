# Working on this repository

## Fast feedback

- `pytest -q` runs in about 12 s: one simulated company (seed 21), the real exports, scripted readers, a fake HTTP
  transport.
- `ruff check . && ruff format --check . && mypy src` for lint and types.
- `python -m paf.cli run dev && python -m paf.cli gate dev && python -m paf.cli report` runs every design on the
  development seeds (about 2 minutes on two cores) and regenerates REPORT.md, the README block, the console data and
  `bi/`.
- `cd web && npm test && npm run typecheck && npm run lint` for the console.

## Invariants

Each one has a test or a CI step.

- **The truth stays in the world.**
  - What the platform gets: the systems' exports (old HRIS, new HRIS, payroll, ATS, exit survey, helpdesk) and the
    People team's answers when it asks.
  - What only the world and the lab's grading may read: who really left and why, real hire and exit dates, the right
    answer to each question, which records are wrong.
  - Test: `tests/test_boundaries.py`, `tests/test_world.py::test_the_exports_carry_no_truth`.
- **The world does not read the platform's settings.** `world/` loads `world.yml` only. `platform/` never imports
  `world` or `lab`.
- **Same luck for every design.** Every draw is keyed by what it is about (`world/luck.py`): a person's exit in a
  month, a record's mistake, the model's reading of a comment. Every design meets the same company, the same records
  and the same model mistakes.
- **One definition for each number.** Every KPI is defined once in `config/kpis.yml`, computed once in SQL, summed up
  the org tree from additive components (never an average of averages). Power BI displays the platform's cells and
  never recomputes them; its DAX is generated from the same catalogue.
- **Adapters refuse and do not guess.** An unknown department or org unit is a question for the People team, never a
  mapping someone invents.
- **The model reads and code decides.**
  - A sensitive question goes to a person before any model reads it.
  - An answer goes out only if its passage exists, the quote is in it, the question names the passage's topic and
    the confidence clears the bar.
  - An exit code counts only if its quote is in the comment, names the theme and is not praise.
  - Prompts carry no worker ids.
- **No cell about fewer than 5 people is published, directly or by subtraction.** Test:
  `tests/test_kpis.py::test_no_small_group_is_published_or_derivable`.
- **A pilot is read out against a control group.** Requesters are assigned by a hash of their id; the effect has a
  bootstrap interval over requesters.
- **Settings live in `config/`**, by owner:
  - the world in `world.yml`;
  - the platform in `platform.yml` and `kpis.yml`;
  - the designs in `designs.yml`;
  - seeds in `seeds.yml`;
  - thresholds in `gates.yml`.
- **Reports are generated, never edited.** CI regenerates `reports/dev.json`, REPORT.md, the README block,
  `web/public/data/report.json` and `bi/`, and fails on a diff.

## Held-out seeds

- `config/seeds.yml` lists them. They run in the held-out world (`world.yml: heldout`), which:
  - makes every system mistake 1.5 times as often;
  - grows the company 30% faster;
  - opens a new engineering team in Poland, unknown to the platform's maps;
  - writes a third of exit comments and questions in phrasings the reader was not tuned on.
- `python -m paf.cli run heldout` writes `reports/heldout.lock` first and refuses to run again (exit code 3).
- CI checks that the lock was committed once.
- Gates are fixed on the development seeds before the held-out run. A new held-out run needs new seeds and an ADR.
