# Timeline

Three weeks, four people. ~240 person-hours available against ~140 hours of
work — genuine slack, but it is not evenly usable.

Tasks are in [implementation-plan.md](implementation-plan.md).

---

## The one hard constraint

**The judge's free tier is 100 requests per day.** No amount of people changes
this. It is wall-clock time, not effort.

The judge runs once per round, so judge calls per case:

| Arm | Rounds | Judge calls |
| --- | --- | --- |
| A `raw` | 1 | 1 |
| B `rag` | 1 | 1 |
| C `single_attacker` | 2 | 2 |
| D `full_council` | 3 | 3 |
| E `self_consistency` | 1 | 1 |
| | | **8 per case** |

| Cases | Judge calls | Days at 100/day |
| --- | --- | --- |
| 20 | 160 | 1.6 |
| 40 | 320 | 3.2 |
| **60** | **480** | **~5** |

A 60-case scored run needs **five clear days**, and that assumes nothing fails
midway. Budget seven.

### What follows

- **Code freeze is day 14, not day 21.** The last week belongs to the scored run.
- The rehearsal (T4-4) runs on a **local judge** and costs no quota. Breakages
  must be found there, not during the real run.
- If the real run breaks on day 17, there is time to fix and restart. On day 20
  there is not.

---

## Week 1 — days 1–5

**Goal: the system runs, and the corpus pipeline is under way.**

| Day | What lands |
| --- | --- |
| 1 | The four decisions (D1–D4) agreed as a group. T0-1 credentials. T1-1 locator ADR. T2-1 started. Everyone writes 1–2 fixtures. |
| 2 | **T0-3: first live debate.** T0-5 recorded fixture → unblocks frontend. T1-2 ICRC parser started. |
| 3 | T0-4 live tests. T3-1 replay harness. T2-2, T2-3 metric tests. |
| 4–5 | T1-2 parser lands. T1-4 chunking started. T2-4/T2-5 Arm E. T3-2/T3-3 verification. |

**End of week 1 — all of:**

- [ ] A real run artifact exists in `data/runs/`
- [ ] The four decisions are recorded as ADRs
- [ ] Metrics have tests (T2-1, T2-2, T2-3 done)
- [ ] The frontend runs from the recorded fixture
- [ ] ≥15 fixtures written

> **If the first live debate has not run by end of day 3, stop and swarm it.**
> Everything downstream assumes the graph works. Discovering otherwise in week 3
> is the one failure this plan cannot absorb.

---

## Week 2 — days 6–10

**Goal: corpus indexed, harness running, fixtures complete.**

| Day | What lands |
| --- | --- |
| 6–7 | T1-4 chunking, T1-5 embed/upsert. T4-1 `run.py` started. T3-4/T3-5 frontend tests. |
| 8 | T1-6 citation index. **I3 integration: the index shape is real.** |
| 9 | T1-7 end-to-end corpus test. T4-2 retrieval exclusion. |
| 10 | T4-3 report generation. Fixtures finished and reviewed. |

**End of week 2 — all of:**

- [ ] `make corpus` populates Qdrant and the citation index
- [ ] All four citation statuses are produced by a real run
- [ ] `make eval-arm ARM=rag` works
- [ ] 40–60 fixtures validated and reviewed for holding-leakage
- [ ] `npm test` passes in CI

---

## Week 3 — days 11–15

**Goal: rehearse, then run for real.**

| Day | What |
| --- | --- |
| 11 | **T4-4 rehearsal — local judge, all five arms, ≥10 cases.** Fix whatever breaks. |
| 12 | Rehearsal again if needed. Report renders end to end. |
| **13** | **CODE FREEZE.** Only fixes to what the scored run needs. |
| 14 | Scored run begins. Arms A, B, E first — cheapest, so failures surface early. |
| 15 | Arms C and D. |

**Days 16–19: the scored run continues.** ~100 judge calls a day. Nothing to do
but monitor and fix.

**Days 20–21: write up.** Report, numbers, limitations.

---

## Reserved vs available

| Days | Status |
| --- | --- |
| 1–13 | Available for building |
| 14–19 | **Reserved for the scored run.** Quota-bound. |
| 20–21 | Write-up |

Slack is in days 1–13. If a track finishes early, see "If a track runs early" in
the plan — the answer is almost always more fixtures.

---

## What gets cut, in order

If day 13 arrives and not everything is done, cut in this order. Each line costs
less than the one below it.

1. **Tier 2 case documents** — the 8 tribunal judgments. Already out of v1 scope.
2. **Frontend polish** — sprite artwork, export formatting.
3. **Held-out set size** — run on 40 instead of 60. Costs ~2 days of quota and
   widens intervals. Say so in the report.
4. **Arm E** — report D-vs-B with the compute confound as a stated limitation.
   Painful: it is what makes Objective 2 falsifiable.
5. **The real corpus** — fall back to the hand-built index.

**Never cut:** metric tests, holding-leakage review, recording which judge
backend was used. Each of those silently invalidates the numbers rather than
visibly reducing them.

---

## Standing checkpoints

| When | Check |
| --- | --- |
| Daily | Which task each person is on; anything blocked >1 day |
| End of day 3 | **Has a live debate run?** If no → swarm it |
| End of day 10 | **Are fixtures done?** If no → everyone writes fixtures until they are |
| Day 13 | Code freeze. What is not merged is cut |
| Day 14 | Quota clock starts |
