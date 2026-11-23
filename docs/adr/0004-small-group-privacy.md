# 0004: No cell about fewer than five people, directly or by subtraction

## Status
Accepted.

## Context
Team-level turnover, pay and exit figures about three or four people identify them. Hiding a small team's cell is not
enough. If its department total and the other teams are shown, the hidden cell is the difference.

## Decision
- Primary suppression: a cell about fewer than 5 people is not published.
- Complementary suppression: if one child of a shown parent is hidden, the smallest other child is hidden too,
  repeated until stable.
- The study attacks the published table: direct small cells, and hidden cells recovered by subtraction.
- No individual-level risk score is published; retention forecasts are by department.

## Consequences
- More cells are hidden, and the console marks why each one is.
- Differencing over time (one month's headcount minus the last) is not covered; the README says so.
