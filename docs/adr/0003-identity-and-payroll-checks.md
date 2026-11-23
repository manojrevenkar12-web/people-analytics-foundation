# 0003: Link both HRIS, and check them against payroll

## Status
Accepted.

## Context
The migration to the new HRIS reset many hire dates to the go-live date. It carried the old system's mistakes
across: contractors recorded as employees, leavers never given an exit date. The old system had also typed notice
dates where last days belonged. Each mistake moves headcount, hires, turnover and tenure-based features.

## Decision
- Identity: an old-HRIS employment and a new-HRIS record are the same when name and birth date match. A rehire keeps
  separate employments, paired on hire date or in migration order.
- Code settles what the systems can settle: hire dates restored from the old HRIS, contractors on external cost
  centres reclassified, stale requisitions closed.
- Payroll is the reference for employment. Someone unpaid for two months without recorded leave, or paid after their
  recorded last day, goes to the People team. The team says whether they left, and when, or were on leave nobody
  recorded. Every question costs review minutes, counted in the study.
- Unknown department names and org units are asked about, never guessed.

## Consequences
- Without identity the payroll checks raise many false alarms, and analyst hours rise accordingly (see the
  `no_identity` ablation).
- With identity but without the checks, the reset hire dates erase people's history before go-live. That design is
  worse than spreadsheets (`no_quality`).
