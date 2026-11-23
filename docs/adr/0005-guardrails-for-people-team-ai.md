# 0005: Guardrails for the People team's AI pilots

## Status
Accepted.

## Context
A helpdesk assistant that answers pay disputes, conflicts or security-clearance questions harms people. One that
quotes the wrong policy is worse than a slow human answer. An exit-comment coder that reads praise ("my manager was
great") as the reason for leaving distorts the retention picture leaders act on.

## Decision
- Sensitive topics are matched by a keyword rule before any model call and go straight to a person.
- The model must name a passage, quote it and state its confidence. Code sends the answer only if all of these hold:
  - the passage exists;
  - the quote is in it;
  - the question names the passage's topic;
  - the confidence clears 0.7.
- For exit comments, the quote must be in the comment, name the theme and not be praise.
- Everything else goes to a person, with the minutes counted.

## Consequences
- On the development seeds the assistant answered wrongly less often than the People team by hand (1.3% against
  2.9%), and took 42% of the minutes off the People team.
- The keyword rule is brittle against new phrasings (ADR 0007).
