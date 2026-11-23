# 0012 — The scored evaluation is three cases, with three more as a stretch

**Status:** Accepted
**Date:** 2026-11-14
**Amended:** 2026-11-20 — the case set is twenty: an `extended` tier of fourteen
adds eight real cases, five fictional ones and Boškoski. See "Amendment: twenty
cases, five of them fictional" below. The core, stretch and scored run are unchanged.

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

## Amendment: twenty cases, five of them fictional (2026-11-20)

Seven cases left two gaps the write-up had to state rather than fix: five of
the seven were affirmed, so a system that always says "yes" scored 71%; and all
were well-known judgments, so a model could recall an outcome instead of
reasoning to it. Thirteen new cases close both, as far as cases can.

**Decision.** `cases/dev/` holds twenty cases. A third tier, `extended`
(`EXTENDED_CASE_IDS`), holds the thirteen new cases and Boškoski, interleaved by
outcome so a run stopped partway still covers a spread; `--tier all` is all
twenty. Every fixture is in exactly one tier (`test_case_tiers.py`).

| | Before | After |
| --- | --- | --- |
| Outcomes | 5 affirmed, 2 rejected | 10 affirmed, 8 rejected, 2 indeterminate |
| Courts | ICTY 6, ICC 1 | ICTY 9, ICJ 3, ICC 2, SCSL 1, fictional 5 |
| Difficulty | 4 medium, 2 contested, 1 hard | 9 medium, 8 contested, 2 settled, 1 hard |

**Eight real cases**, each checked against the tribunal's own text or its
official summary: Prlić (Old Bridge of Mostar), Orić, Halilović, Ntaganda
(crimes within one's own armed group), Norman (SCSL, child recruitment),
Croatia v. Serbia, and the ICJ's Wall and Nuclear Weapons opinions. Nuclear
Weapons is the one real indeterminate: the Court could not conclude either way
for an extreme circumstance of self-defence. Wall and Nuclear Weapons set
`source_case_id` because those opinions are in the corpus manifest.

**Five fictional cases** (`hyp_`, court `Hypothetical`): invented states,
places and events, real treaty law. No model can recall their outcomes, so they
are the only cases that test reasoning rather than memory. Their ground truth is
**authored**, not adjudicated: it is our reading of the law on facts written to
make that reading clear, or, for `hyp_cluster_shared_control`, written to sit on
a question the treaty text leaves open. Each `holding` starts "Authored ground
truth" so no reader mistakes it for a ruling. They cover perfidy, loss of
protection by a hospital, the Cluster Munitions Convention's interoperability
clause, prisoner-of-war status of a militia, and starvation.

**Still true.** Twenty is below the 40–80 at which arm differences become
measurable; the report will print intervals, and they will be wide. All twenty
are dev cases: there is still no held-out set. Results on the fictional cases
should be reported separately as well as pooled, since their ground truth is of
a different kind. The scored run (#26) was the core and Mrkšić, under the
frozen settings; the new cases run under the same settings.
