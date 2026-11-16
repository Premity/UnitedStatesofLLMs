# Prompt tuning log

Run each experiment on the same dev subset and record the prompt file's hash
from the result artifact or report. Keep held-out cases out of prompt tuning.

| Date (UTC) | Prompt file changed | Prompt hash | Cases used | Judge calls used | Accuracy | Brier | ECE | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-11-12 | `prompts/judge/rule.md` | `69c27d4fbb` | 0 | 0 | - | - | - | Require explicit Yes/No/Indeterminate prefix; no evaluation metrics claimed. |
| 2026-11-12 | — (outcome parser in `evaluation/harness/run.py`) | — | 0 | 0 | - | - | - | Handle negation conservatively and return indeterminate when unclear; no evaluation metrics claimed. |
| 2026-11-12 | — (judge JSON mode in `packages/council-core/src/council_core/llm/client.py`) | — | 0 | 0 | - | - | - | Request JSON mode for structured judge calls; no evaluation metrics claimed. |
| 2026-11-16 | `prompts/judge/rule.md` (+ scorer fix, case facts; see below) | `6854889d75` (set `0455e4cb3248`) | 3 | 16 | B 0.33 · C 0.67 · D 0.67 | B 0.46 · C 0.22 · D 0.19 | B 0.57 · C 0.20 · D 0.18 | One run per arm and case; not separable, see below. |
| 2026-11-16 | `prompts/shared/_citation_rules.md`, both attacker `challenge.md` (+ citation format check) | set `e687486954b3` | 2 of 3 | 10 | C 0.50 · D 0.50 (Gotovina errored) | - | - | Citation format fixed; exposed the judge prompt silencing the evidentiary attacker. See below. |
| 2026-11-16 | `prompts/judge/rule.md` ("Weighing the facts" removed) | `aa219aad89` (set `f8a652539767`) | 3 | 7 | D 1.00 (3 of 3) | - | - | D only; C on Bemba hit a Groq limit. One run each. See below. |


## Judge prompt corrected: the full council on its own facts fix, 2026-11-16

**Change.** The first fix's "Weighing the facts" paragraph is removed from the
judge prompt; "Answering the question" stays. With the citation fix in place,
this isolates the case-facts change as the remaining fix for Galić.

**Result** (D on the three core cases, `data/scratch/tune-03`, 7 judge
attempts):

| Case (truth) | D | Evidentiary objections (sustained / partial / overruled) | Unresolved |
| --- | --- | --- | --- |
| Galić (affirmed) | affirmed 0.75 | 2 / 3 / 2 | 0 / 36 |
| Bemba (rejected) | rejected 0.68 | 0 / 2 / 3 | 1 / 18 |
| Gotovina (rejected) | rejected 0.75 | 7 / 0 / 0 | 0 / 13 |

- **The full council answered all three correctly**, the first time any arm
  got Gotovina right. Galić stays right without the judge being pushed toward
  Yes, so the case facts were the fix it needed.
- **The evidentiary attacker is back in play**: sustained or partly sustained
  in Galić and Gotovina, and decisive in Gotovina, an appeal about whether the
  evidence supported the trial findings.
- **The one unresolved citation is a real mis-citation**: the presenter quoted
  AP I art. 86(2) verbatim but filed it under `customary_ihl`. It is well
  formed, so the format check rightly lets it through, and the metric rightly
  counts it.
- **C on Bemba did not run**: Groq rate-limited the presenter's model
  (`openai/gpt-oss-120b`) on this account after a day of runs. C under this
  prompt is untested.

One run per case, on the scored cases. Together with the first fix's run it
shows the debate arms now reach the tribunal's answer where they did not, not
how reliably. C needs a run under this prompt before the set is frozen for
#26.

## Citation format fix, and a judge prompt that overcorrected, 2026-11-16

**Change.** Attacker and presenter replies reject a malformed citation (wrong
type for its fields, or a locator in `instrument`) and the repair prompt sends
it back; both attacker reply examples now show a treaty citation; the shared
citation rules say to copy the locator exactly as the context heading gives
it. What the fabrication metric counts is unchanged.

**Result** (C and D on the three core cases, `data/scratch/tune-02`, judge
prompt `6854889d75` unchanged from the first fix):

| Case (truth) | C | D | Unresolved, D (before → after) |
| --- | --- | --- | --- |
| Galić (affirmed) | affirmed 0.85 | affirmed 0.85 | 8 / 20 → 0 / 23 |
| Gotovina (rejected) | error | error | — |
| Bemba (rejected) | **affirmed** 0.75 | **affirmed** 0.75 | 2 / 21 → 0 / 21 |

- **The citation fix worked**: no unresolved citation in any completed run,
  and the repair prompt never had to fire; the examples were enough. The
  presenter's `8(b)(ii)` near-miss went untested: it was Gotovina-specific.
- **Gotovina errored twice on Groq**, not the change: the doctrinal attacker's
  model (`qwen/qwen3.8-27b`) is limited to 1,000 output tokens per minute on
  this account's tier, and Groq judged the request at 3,745. The same call
  passed earlier the same day. The two machines share a roster, not Groq
  limits.
- **Bemba flipped to Yes in both debate arms**, and the rulings show why. How
  the judge ruled on the evidentiary attacker's objections:

  | Judge prompt | Run | Sustained | Partial | Overruled |
  | --- | --- | ---: | ---: | ---: |
  | before the first fix | Galić D, rehearsal 1 | 3 | 2 | 3 |
  | before the first fix | Galić D, rehearsal 2 | 4 | 2 | 0 |
  | `6854889d75` | Galić D, first fix | 0 | 0 | 10 |
  | `6854889d75` | Bemba D, first fix | 0 | 2 | 3 |
  | `6854889d75` | Galić D, this run | 0 | 0 | 7 |
  | `6854889d75` | Bemba D, this run | 0 | 0 | 7 |

  Under the first fix's judge prompt not one evidentiary objection was
  sustained. Its "Weighing the facts" paragraph said an objection that
  something is not established "succeeds only if the facts do not support the
  inference", a bar the attacker cannot clear. That silences one of the two
  attackers and tilts the judge toward Yes, the wrong answer in two of the
  three cases. Bemba turns on whether the evidence established a failure to
  take measures: the evidentiary attacker's mandate.

**Next.** The paragraph is removed (judge prompt `aa219aad89`); "Answering the
question" stays. That leaves the case facts as the remaining fix for Galić,
which the next run tests on its own.

## Council diagnosis and first fix, 2026-11-16

**Problem.** In the #25 rehearsals the debate arms answered Galić wrongly while
`rag` answered it right: C once and D twice concluded "war crimes, but the
crime of terror is not established on this record". Diagnosed from the
rehearsal artifacts:

- Every wrong debate verdict made the same move: the attackers objected that
  the facts did not establish the *primary purpose* of spreading terror, and
  the judge sustained it. The case's `facts` were thinner than the tribunal's
  findings: they omitted that the campaign had no discernible military
  significance, the finding the tribunal inferred purpose from.
- The outcome parser misread two explicit answers ("Indeterminate." as
  rejected, "No." as indeterminate). Fixing it changed no accuracy: the "No"
  answers were real.
- Ruled out: the judge never treated `out_of_corpus` as unsupported.
- Retrieval did not leak the answer (no judgments are indexed), but models
  recognise these famous cases from pretraining; that applies to every arm.

**Changes, all at once:** the parser trusts the judge's opening answer; Galić
and Gotovina `facts` gained the factual findings their `key_reasoning` relies
on (taken from the case file, never the question's own finding; Bemba had none
to add); and the judge prompt now says to infer intent from the facts as a
whole, to the question's standard, and that sustaining an objection is not by
itself an answer of No. The rehearsals also predate the #39 customary-rule fix.
These are not separable from one run.

**Result** (`rag`, `single_attacker`, `full_council` on the three core cases,
one run each, `data/scratch/tune-01` on the second machine, same roster and
index as the first):

| Case (truth) | B rag | C one attacker | D full council |
| --- | --- | --- | --- |
| Galić (affirmed) | affirmed 0.95 | affirmed 0.88 | affirmed 0.78 |
| Gotovina (rejected) | affirmed 0.88 | affirmed 0.75 | affirmed 0.65 |
| Bemba (rejected) | affirmed 0.78 | rejected 0.72 | rejected 0.68 |

Galić D raised the same primary-purpose objections and the judge now answered
Yes. Every arm misses Gotovina, an appeal that reversed the trial findings the
`facts` report; the council is the least confident of the three about it.

**New problem this exposed.** C and D's fabrication rate rose (0.13, 0.23).
Every unresolved citation checked is a real authority, malformed: the
evidentiary attacker cites treaty articles as `"type": "case"` with the
locator in `instrument` (all 8 of Galić D's), and the presenter drops the
paragraph from Rome Statute locators (`8(b)(ii)` for `8(2)(b)(ii)`). Neither
is invention, and both count as fabrication. To fix before the scored run.

Three cases, one run each, and all of them the scored cases: this shows the
direction changed, not by how much.

## Rehearsal: arms A-E live on one case (#25), 2026-11-15

> **Both rehearsal runs predate #39.** Every customary rule in arms B-E's
> retrieved context was labelled `customary_ihl/rule.None`, so their outcomes
> and citation counts are not evidence about the fixed system. They still
> show what broke in the harness.

Case `icty_galic_terror`, full corpus (index `8ffefb5a30ab`, 24 instruments, 3482
locators), judge `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`. No prompt
was changed. 7 judge calls, 7 of 40 attempts, no judge failures.

| Arm | Predicted (truth: affirmed) | Confidence | Judge calls | Time |
| --- | --- | ---: | ---: | ---: |
| A raw | affirmed | 0.75 | 1 | 36 s |
| B rag | affirmed | 0.92 | 1 | 40 s |
| C single_attacker | rejected | 0.70 | 2 | 274 s |
| D full_council | indeterminate | 0.70 | 2 | 268 s |
| E self_consistency | affirmed | 0.71 | 1 | 290 s |

One case: these rows support no claim about the arms. Checks from #25:

- **Every arm completed**, but not unattended. Two interventions, below.
- **E's sample count matches D's call count.** D made 8 calls, E ran 7 presenter
  samples plus 1 judge call, 8 in all.
- **Citations plausible.** No `unresolved` in any arm. C had 5 `out_of_corpus` and
  2 `misquoted` of 17; D had 4 `out_of_corpus` of 16.
- **Both attackers return `severity`.** All 18 objections in C and D carry a
  parseable value (fatal, material or minor); none came back unstated.
- **Judge calls within the tracker.** A 1, B 1, C 2, D 2, E 1 = 7, matching the
  quota log.

What broke:

1. **Arms B-E failed at retrieval on the first pass.** `.env` has
   `QDRANT_URL=http://qdrant:6333`, which the host cannot resolve. Fixed per
   run with `QDRANT_URL=http://localhost:6333`; documented in
   `docs/development.md`. Arm A succeeded, so the failure looked partial.
2. **Arm E timed out at the default 300 s** with 5 of 7 samples done. Samples run
   one after another against Groq, and the log shows retry backoff. Re-run with
   `--case-timeout 900` and `--resume`; it finished in 290 s. C and D also took
   270 s or more, because the free judge took 120-138 s per call in rounds 2 and
   3. The 300 s default leaves no margin. Needs its own issue: raise the default
   or sample in parallel.
3. The `--case` help text said 24 reserved attempts per case; it is 21
   (7 calls x 3). Fixed.

## Rehearsal, run 2: after the fixes, 2026-11-15

The same case, index and roster, run with no `QDRANT_URL` override and no
`--case-timeout`, on the fixes since merged as #40: a host run reaches Qdrant at
`localhost`, and the per-case timeout is 900 s. Run 1's results are kept in
`data/eval-rehearsal-1/`. 9 judge attempts, one of them a failed repair.

| Arm | Predicted (truth: affirmed) | Confidence | Judge calls | Time |
| --- | --- | ---: | ---: | ---: |
| A raw | affirmed | 0.75 | 1 | 29 s |
| B rag | affirmed | 0.92 | 1 | 46 s |
| C single_attacker | affirmed | 0.78 | 2 | 149 s |
| D full_council | rejected | 0.78 | 2 | 332 s |
| E self_consistency | affirmed | 1.00 | 1 | 350 s |

- **Both fixes held.** Arm B retrieved with no override. D (332 s) and E (350 s)
  would both have timed out at 300 s.
- **E's count still matches D's.** D made 8 calls, E ran 7 samples and 1 judge
  call.
- **A new failure in arm E.** In the first pass the judge returned a
  `conclusion` but no `reasoning` and no `confidence`. The repair attempt came
  back the same way, so E errored after 308 s. The raw reply was not stored, so
  how the model got it wrong is unknown. The client now logs the raw reply on a
  failed parse or a repair. E passed on a re-run of that arm alone
  (`--arm E --resume`). If it recurs, the log decides the fix: a clearer schema
  example in `prompts/judge/`, or a second repair, which the 3-attempt
  reservation already budgets for.
- **Arms C and D differ between runs.** C went from `rejected` to `affirmed`, D
  from `indeterminate` to `rejected`. Run-to-run variance at temperature on one
  case; no conclusion.
- **Timings** for both runs are in `docs/evaluation.md`, *Running it*: about
  15 minutes per case through all five arms.

## How to run an experiment

1. Change exactly one file under `prompts/`.
2. Run the same arm on the same dev subset, using a fresh output directory so
   results from different prompt versions are not overwritten. For example:

   ```bash
   make eval-arm ARM=rag ARGS="--limit 5 --judge-backend local --output-dir data/eval/prompt-test-01"
   uv run python -m metrics.report --results-dir data/eval/prompt-test-01 --output evaluation/reports/prompt-test-01.md
   ```

3. Add a row above with the changed prompt file and its hash, cases run, judge
   calls used, accuracy, Brier score, ECE, and any relevant notes.
