# 0002: One definition for each number, computed once

## Status
Accepted.

## Context
In spreadsheet reporting each analyst writes their own turnover formula. One counts every leaver over the month-end
headcount, another only voluntary leavers over the average headcount. A department average of team percentages is
not the department's percentage. Two reports then disagree and leaders stop trusting both.

## Decision
- The catalogue (`config/kpis.yml`) defines each KPI once, with an owner and a plain definition.
- SQL in DuckDB counts additive components per team and month. They are summed up the org tree, and each KPI is
  computed from the sums at every level.
- Power BI gets the computed cells (privacy already applied) in a star schema. Its DAX is generated from the same
  catalogue and only selects values.

## Consequences
- A new KPI needs additive components; a median (time to fill) is computed per node from the underlying rows.
- The study grades every published cell against the truth computed with the same definitions.
