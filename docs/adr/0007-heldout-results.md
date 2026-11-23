# 0007: Held-out results

## Status
Accepted. Run once on 23 Nov 2026 (seeds 201 and 202).

## Context
AGENTS.md describes the held-out world. The gates in `config/gates.yml` were fixed on the development seeds.

## Results
**7 of 9 gates passed.**

- **The numbers held up.** 99.8% of published KPI cells matched the truth, against 68.7% for spreadsheets. That is
  despite system mistakes 1.5 times as often and a new Polish team the maps did not know (the People team was asked
  and the team mapped).
- **No cell about fewer than 5 people was revealed.** Spreadsheets revealed 592. Hiding small groups without
  protecting their siblings revealed 565 by subtraction.
- **The pilot readout covered the true effect** in both seeds: 4.5 People-team minutes saved per question, estimated
  at 4.8.
- **Analyst hours** were 6.7 a month against 49.

## What failed
- **Sensitive questions reached the model: 87 across both seeds.** The keyword rule knew the development phrasings
  only. "I found out the new hire earns more than me", "I do not feel safe raising things in my team" and "Has my
  vetting come back yet?" passed it.
  - The other checks still kept every one of those answers from going out.
  - But the model read text a person should have read first.
  - The fix is a sensitivity classifier tuned to miss nothing, with a person as the default for anything about pay,
    a manager, health or clearance. Not applied: it needs new held-out seeds.
- **The hiring forecast was 0.90 of the trailing-average error, against a gate of 0.85.** The company grew 30% faster
  than in development, and requisitions opened after the origin filled within the window. The forecast only counts
  requisitions already open.
- **The retention model barely beat the trailing average** (0.98 of its error; the gate was "no worse"). The strongest
  cause of leaving, a weak manager, is not in any HR system.

## Contaminated, and reported anyway
- **The exit-coding and helpdesk-topic word lists include words from the held-out phrasings.** These are
  `exit_coding.cues` and `helpdesk.passage_topics` in `config/platform.yml`. I wrote them after writing both phrasing
  sets.
- The held-out exit-coding accuracy (100%) and assistant wrong-answer rate (1.5%) are therefore not out-of-sample
  results.
- The sensitive-topic rule was deliberately kept to the development phrasings, which is why it failed.

## Consequences
- The next run needs new seeds and new phrasings written by someone who has not seen the word lists.

## Found after the run
- **An empty org node triggered extra hiding.** "Unmapped" had nobody in it, but counted as a hidden cell, so the
  sibling-protection rule also hid a department (G&A, about 22 people). That over-protects rather than leaks.
- Fixed after the run: a cell about nobody no longer counts as hidden. `tests/test_kpis.py` covers it.
- The development numbers were regenerated. The held-out report keeps what came out.
