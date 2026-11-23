# 0001: A simulated company that keeps its own truth

## Status
Accepted.

## Context
People analytics is judged by whether its numbers are right and its predictions hold. With real HR data nobody knows
the right answer: the HRIS is the thing under test. Real employee data could not be shared in a public repository
anyway.

## Decision
- `world/company.py` simulates the company month by month: hires against a workforce plan, transfers, pay reviews,
  promotions, parental leave, and voluntary exits driven by causes the HR systems do not record (a weak manager, pay
  below band, the first six months, overtime season, no promotion for a long time).
- `world/systems.py` writes what each system records, with mistakes at configured rates: the old HRIS (German
  fields), the migration, the new HRIS, payroll and the ATS.
- `world/texts.py` writes exit comments and helpdesk questions; their real reasons and right answers stay in the world.
- `world/truth.py` builds the canonical model from the truth, so every design's KPIs are graded cell by cell.

## Consequences
- Results hold under the world's assumptions only. The kinds of mistakes are ones HR teams meet in HRIS migrations;
  their rates are chosen.
