# 0006: Read pilots out against a control group

## Status
Accepted.

## Context
"Before and after" readouts mix the tool's effect with everything else that changed: in this world the pilot starts
during an onboarding wave, with more routine questions and a slower People team.

## Decision
- During the pilot months, requesters are assigned to the assistant or to the People team by a hash of their id
  (stable, about half each).
- The effect is the difference in means between the groups, with a 95% bootstrap interval over requesters.
- The world knows both outcomes for every question, so the study compares each readout with the true effect.

## Consequences
- The randomised interval covered the true time saved in every development and held-out seed.
- The before/after estimate missed in one of three development seeds, but by less than I expected; in this world the
  onboarding wave is a small bias.
