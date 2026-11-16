# The scored run: what three cases show, and what they cannot

Scored run of 2026-11-16 (GitHub #26). The numbers are in
[evaluation-report.md](evaluation-report.md), from the three core cases, and in
[evaluation-report-with-stretch.md](evaluation-report-with-stretch.md), which
adds the one stretch case run. The result files behind both are in
[`evaluation/results/scored-run/`](../results/scored-run/).

**This is a demonstration, not a statistical result.** Three cases, all seen
while the prompts were tuned, support no claim that one arm beats another. The
report prints no confidence intervals below 10 cases, and this write-up reads
the results case by case for the same reason. The limits are listed in full
under [Limits](#limits).

---

## What was run

All five arms of the ablation ladder (`docs/evaluation.md`) on each case, one
case per command, every call live:

| Arm | What it is |
| --- | --- |
| A `raw` | The presenter argues from the facts alone, then the judge rules. No retrieval. |
| B `rag` | As A, with retrieved treaty and case-law context. |
| C `single_attacker` | B plus the doctrinal attacker, up to 2 rounds. |
| D `full_council` | C plus the evidentiary attacker, up to 2 rounds. |
| E `self_consistency` | B, with the presenter sampled 7 times (D's calls minus the judge) and one judge call. |

The cases (`evaluation/cases/dev/`):

| Case | Tier | Question | Tribunal's answer |
| --- | --- | --- | --- |
| `icty_galic_terror` | core | Was the campaign of sniping and shelling against Sarajevo's civilians the crime of terror? | affirmed |
| `icty_gotovina_knin` | core | Were the artillery attacks on Knin, Benkovac, Obrovac and Gračac unlawful? | rejected: the Appeals Chamber reversed the trial finding |
| `icc_bemba_command` | core | Is the commander responsible under Rome Statute art. 28(a) for his troops' crimes? | rejected: the Appeals Chamber reversed the conviction |
| `icty_mrksic_vukovar` | stretch | Is the commander responsible for the killing of the prisoners taken from Vukovar hospital? | affirmed |

Every result ran on the frozen settings (ADR 0009, fingerprint
`df941348ab17`), which the report's header lists in full:

- presenter `groq/openai/gpt-oss-120b`
- doctrinal attacker `groq/qwen/qwen3.8-27b`
- evidentiary attacker `groq/openai/gpt-oss-20b`
- judge `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
- prompt set `8205576bb484`, embedding `BAAI/bge-large-en-v1.5`
- citation index `8ffefb5a30ab` (24 instruments, 3,482 locators)

The cases ran on two machines with the same settings and the same index, as the
runbook (`docs/runbook-evaluation.md`) intends. All 20 runs completed: no
errors, no timeouts, no `--resume`. Each case used 7–8 judge attempts.

---

## Results

| Case (truth) | A raw | B rag | C one attacker | D full council | E self-consistency |
| --- | --- | --- | --- | --- | --- |
| Galić (affirmed) | ✓ 0.88 | ✓ 0.95 | ✓ 0.88 | ✓ 0.75 | ✓ 0.95 |
| Gotovina (rejected) | ✗ 0.65 | ✗ 0.85 | ✗ 0.78 | **✓ 0.72** | ✗ 0.78 |
| Bemba (rejected) | ✗ 0.85 | ✗ 0.70 | ✗ 0.68 | ✗ 0.70 | ✗ 0.85 |
| *Mrkšić (affirmed), stretch* | ✓ 0.85 | ✓ 0.92 | ✓ 0.75 | ✓ 0.75 | ✓ 0.88 |

Each cell is whether the arm matched the tribunal, and the judge's stated
confidence. On the three core cases D is right on two and every other arm on
one. With the stretch case, D is right on three of four and the others on two.

### Every arm affirms; only the council ever says no

Of the 20 runs, 19 answered *affirmed*. The two cases the tribunals answered
*rejected* are both appeals that reversed a conviction or a trial finding, and
every arm without the evidentiary attacker affirmed both. The one *rejected* in
the whole run is D on Gotovina.

This is the bias the design expects. The presenter argues for the proposition,
so a judge that sees only the presenter sees one side. An affirming answer on
the two affirmed cases says little about any arm.

### Gotovina: the evidentiary attacker turns the answer

C and D share the 2-round ceiling, the same presenter, the same doctrinal
attacker and the same judge; they differ only in the evidentiary attacker. C
affirmed at 0.78. D rejected at 0.72, with all 7 evidentiary objections
sustained: the record did not show the towns' defended status, any weighing of
the military advantage expected against the harm to civilians, or verification
measures available and not used. That is close to the ground the Appeals
Chamber reversed on, that the trial findings did not support the conclusion the
attacks were unlawful. D's dissent log on Gotovina is empty: the judge overruled
nothing.

This is also the case the tuning was watched on. `tuning/LOG.md` records D
first getting Gotovina right after the case-facts fix (`tune-03`), so this run
confirms the fix held under the frozen settings. It is not independent evidence
that it works.

### Bemba: the council raised the right objection, and the judge overruled it

Every arm affirmed Bemba, D included. The dissent log is what shows the most
about it. The evidentiary attacker objected, rated *fatal*, that "the record
fails to show that the commander failed to take all necessary and reasonable
measures within his power". That is the ground on which the Appeals Chamber
majority reversed the conviction. The judge overruled it: crimes continued
despite the measures taken, and other commanders exercised discipline in the
field, so stronger measures were within his power. That is the Trial
Chamber's reasoning, which the appeal rejected.

D's judge overruled 7 objections on Bemba, 3 of them the same objection on
the commander's knowledge, raised three times. The dissent log records each
with the judge's reasons, which is what it is for: a reader can see that the
council found the right weakness and that the judge was not persuaded. In
tuning (`tune-03`, prompt set `f8a652539767`, two prompt changes before the
freeze) D got Bemba right; one run per case cannot say which outcome is
typical.

### Galić and Mrkšić: no arm needs the council

Both are affirmed, and every arm affirmed them. On Galić D is the least
confident arm (0.75 against 0.88–0.95), after its judge sustained objections
that the Rome Statute was not in force for the events and overruled 3 that said
the record showed no primary purpose to spread terror. On cases where the
answer is *yes*, a council that adds doubt can only cost confidence; whether
that doubt is well placed is what the calibration figures try to measure, and
three cases are too few for them to.

### Calibration

| Arm (core cases) | Brier score | Overconfidence |
| --- | ---: | ---: |
| A raw | 0.386 | 0.460 |
| B rag | 0.405 | 0.500 |
| C one attacker | 0.362 | 0.447 |
| D full council | 0.210 | 0.057 |
| E self-consistency | 0.444 | 0.527 |

Lower is better for both; overconfidence is mean confidence minus accuracy. D
has the lowest of both because it got Gotovina right; it is no less confident
than the others when it is wrong (0.70 on Bemba). With n = 3 each figure moves
by a third of its range when one case changes, so read them as a description of
these three cases.

### Citations

No arm invented an authority. The fabrication rate, `unresolved` over the
citations it applies to (ADR 0004), is 0 for every arm except C, whose 2
unresolved citations of 47 are one real provision misfiled twice: the presenter
quoted AP I art. 86(2) under `customary_ihl` in its Bemba opening and
rebuttal. Tuning saw the same misfiling (`tuning/LOG.md`), and the metric
counts it, rightly, because the locator it gave does not exist.

B misquoted 3 of 13 citations: real provisions, quoted inexactly. The quote
check is a loose token-overlap heuristic, so the misquote rate is reported
apart from fabrication.

---

## Arm E: what changed after the run

Arm E's confidence was meant to be the share of its 7 samples that agreed on
the answer (ADR 0011). The run showed that measure cannot work here, and E's
confidence is now its judge's, as for B. No model was called again.

- **The samples cannot disagree.** The presenter is an advocate: every sample
  argues for the proposition. All 28 samples across the four cases argue
  *affirmed*, so a correct count is 7 of 7 every time, whatever the case.
- **The count was also misread.** A sample states no answer, so the harness
  inferred one from its wording, and read prosecution arguments as denials:
  "the commander *failed to* take all necessary and reasonable measures" was
  counted as a *no*. On Bemba it counted 5 of 7 samples as *rejected*, and E
  was recorded as *affirmed* at 0.714, the agreement on an answer it did not
  give. Mrkšić was misread the same way (5 of 7).

So E's recorded confidence was either 1.0 by construction or a misreading. The
four stored E results were rescored with
`python -m harness.artifacts rescore`, which moves each to its judge's stated
confidence and keeps the original figure as `agreement_rate`, beside the
`vote_counts`. The harness now does the same for new runs. ADR 0011 records
the amendment.

What this does to the comparison: E is now B with seven presenter samples to
choose the arguments from, and its judge sees one of them. It remains a
compute-matched control for D, and on these cases it did no better than B. That
more presenter calls without an adversary did not change a single answer is
the finding E was built to test.

---

## Limits

These are stated here rather than fixed.

- **Three cases, all seen during prompt tuning.** All of them, and the stretch
  case, are dev cases (ADR 0012); there is no held-out set, so nothing here
  measures generalisation. The prompts and case facts were changed while
  watching these cases, Gotovina above all. This is a demonstration, not a
  statistical result.
- **Well-known judgments.** The facts do not name the accused, but places and
  dates identify every case, so a model may recall the outcome rather than
  reason to it. That recall would favour *affirmed* on Galić and Mrkšić; it did
  not lead any arm to the reversals in Gotovina and Bemba.
- **The roster.** The presenter is `gpt-oss-120b`, not the Magistral the design
  named (ADR 0009): Mistral's free tier refused the first request from a new
  account, so Magistral never ran. The presenter and the evidentiary attacker share the
  `gpt-oss` family (120b and 20b), so the two are less independent than two
  model families would be.
- **Three Rome Statute weapons amendments are not indexed.** The source gives
  each inserted sentence with no article number, and a guessed locator would be
  indistinguishable from a fabrication. A citation to one resolves `unresolved`
  and counts against the model. None was cited in this run.
- **The Rome Statute text is our consolidation** of the ICRC base text and the
  2010 amendments, not an official publication (ADR 0010).
- **C and D share a 2-round ceiling** and differ only in the second attacker
  (#23, closed). Neither ran a third round, so round count plays no part in any
  difference between them.
- **Arm E was rescored after the run** (above). Its outcomes are as run; its
  confidence is the judge's, read from the stored results.
- **One run per case.** Models were called at their configured temperatures,
  so a re-run could differ. D answered Bemba correctly in tuning (`tune-03`, on
  slightly earlier prompts) and incorrectly here.

---

## The artifacts

[`evaluation/results/scored-run/`](../results/scored-run/) holds all 20
results, `<arm>/<case>.json`, as the harness wrote them, with two changes:

- **Corpus text removed.** Every `corpus_text` field is dropped
  (`python -m harness.artifacts export`): the repo is public, and nobody has
  checked the redistribution terms of the treaty texts (ADR 0014). Each
  citation keeps its locator, status and source URL, so a reader can look the
  text up.
- **Arm E rescored**, as above; each E file says so in its `rescored` field.

Everything else is as run: each turn's model, prompt hash and raw response,
the arguments, the objections with their severity, ruling and the judge's
reasons, and the verdict. The dissent log behind any number in the report is
the `dissent` list of the matching file.

To rebuild the reports from them:

```bash
cd evaluation
python -m metrics.report --results-dir results/scored-run \
  --output reports/evaluation-report-with-stretch.md
```

The core-only report is built the same way from a folder holding only the three
core cases' 15 files.

---

## What is next

Reasoning overlap (#27): whether each run relied on the grounds the tribunal
gave, scored by hand on the 15 core results. The report has the column; it
reads "not scored" until then.
