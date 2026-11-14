# 0012 — The scored evaluation is three cases, with three more as a stretch

**Status:** Accepted
**Date:** 2026-11-14

## Context

The evaluation was planned at 40–80 cases, split dev / held-out, because below
roughly 40 the bootstrap intervals are too wide for an arm comparison to mean
anything. Seven dev cases exist and no held-out ones; writing more is not
affordable in the time left.

The judge quota sets the pace. The judge is on OpenRouter's free tier, 50
requests a day shared across the account; the harness caps itself at 40
(`MAX_DAILY_QUOTA`). One case through all five arms is up to 7 judge calls
(A 1, B 1, C 2, D 2, E 1; C and D share a 2-round ceiling, GitHub #23), and
before a live invocation starts the harness reserves three attempts per
expected call for repairs and retries: 21 for one
case. An invocation that cannot reserve that much does not start.

## Decision

**Core: three cases**, run through all five arms and scored:

| Case | Question family | Outcome | Difficulty |
| --- | --- | --- | --- |
| `icty_galic_terror` | Lawfulness of attacks | affirmed | medium |
| `icty_gotovina_knin` | Lawfulness of attacks | rejected | contested |
| `icc_bemba_command` | Command responsibility | rejected | contested |

Chosen to cover both question families, both outcomes, and both courts. The two
rejections matter most: in both, a trial conviction was overturned on appeal,
which is the situation the attackers exist for, and a set of only affirmed cases
would score a system that always answers "yes" at 100%.

**Stretch: three more**, run only with judge quota left after the core, in this
order: `icty_martic_zagreb`, `icty_strugar_dubrovnik`, `icty_mrksic_vukovar`.
All medium, to balance a core that is two-thirds contested. A stretch case
counts only once all five arms have completed on it; otherwise the arms would be
compared on different cases.

`icty_boskoski_ljuboten` stays in `cases/dev/` and is in neither tier.

The tiers live in `evaluation/harness/cases.py` (`CORE_CASE_IDS`,
`STRETCH_CASE_IDS`) and are selected with `--tier` and `--case`. Run one case
per invocation: at 21 reserved attempts per case, about two cases fit in a day,
so the core takes two days.

## Consequences

**What the results can claim:** that the method runs end to end on real cases,
and what each arm did on each case. Read per case, the dissent logs are the
deliverable either way.

**What they cannot claim:** any statistical difference between arms. Three cases
give 10 distinct bootstrap resamples, so an interval over them is meaningless.
The report prints none below 10 completed cases and compares the arms case by
case instead.

**Stated in the write-up, not fixed:**

- All six cases are dev cases, seen during prompt tuning. There is no held-out
  set, so nothing here measures generalisation.
- All six are well-known judgments. The facts are written without naming the
  accused, but places and dates identify them, so a model may recall the
  outcome rather than reason to it.

**What would make us revisit it:** time and quota for a held-out set. The
40–80 target and its reasoning stand for any evaluation meant to support a
claim about the arms; this one is not that.
