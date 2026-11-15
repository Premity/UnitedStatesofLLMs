# Prompt tuning log

Run each experiment on the same dev subset and record the prompt file's hash
from the result artifact or report. Keep held-out cases out of prompt tuning.

| Date (UTC) | Prompt file changed | Prompt hash | Cases used | Judge calls used | Accuracy | Brier | ECE | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-11-12 | `prompts/judge/rule.md` | `69c27d4fbb` | 0 | 0 | - | - | - | Require explicit Yes/No/Indeterminate prefix; no evaluation metrics claimed. |
| 2026-11-12 | — (outcome parser in `evaluation/harness/run.py`) | — | 0 | 0 | - | - | - | Handle negation conservatively and return indeterminate when unclear; no evaluation metrics claimed. |
| 2026-11-12 | — (judge JSON mode in `packages/council-core/src/council_core/llm/client.py`) | — | 0 | 0 | - | - | - | Request JSON mode for structured judge calls; no evaluation metrics claimed. |

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
