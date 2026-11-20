# Evaluation

How we test whether the council actually beats a single pass — and how to avoid
fooling ourselves.

---

## The claim under test

> A structured multi-agent debate produces better-calibrated, better-grounded
> legal analysis than a single-pass LLM.

That is three claims, and they need separating:

1. It reaches the right conclusion more often
2. It is **appropriately uncertain** where the question is genuinely contested
3. It fabricates authority less

Claim 2 is the interesting one. A single-pass model on a contested IHL question
is typically confident and sometimes wrong. A council that answers the same
question with 60% confidence and a dissent log listing what it overruled is more
useful *even at the same accuracy*.

---

## The ablation ladder

Five arms. A–D form a ladder, each differing from the one above in exactly one
respect; E sits beside D as a control rather than on the ladder. All five are
defined in `evaluation/harness/arms.py`.

| Arm | Configuration | Isolates |
| --- | --- | --- |
| **A** `raw` | Single pass, no retrieval | The raw baseline |
| **B** `rag` | Single pass + retrieval | What grounding alone contributes |
| **C** `single_attacker` | Presenter + doctrinal attacker + judge | What adversarial challenge contributes |
| **D** `full_council` | Both attackers | Whether the second attacker earns its place |
| **E** `self_consistency` | One model sampled *n* times and aggregated, *n* matched to D's call count | Whether D's gain comes from adversarial structure or merely from more compute |

C and D both run at most 2 rounds, so they differ only in the second
attacker. That is the app's default too, so the evaluation scores what the app
runs. A third round can be chosen in the app; it is not evaluated.

B exists so the council is not credited for gains that retrieval alone produces.
Without it, "our system beats a raw LLM" is an uninteresting claim.

E exists for the same reason one step further out. A debate spends several model
calls per question, and the multi-agent debate literature has been criticised for
not establishing whether its reported gains come from the adversarial structure
or from the extra computation that structure consumes. Comparing D against B
alone inherits that weakness; comparing D against a compute-matched baseline does
not. **E is the arm that makes the central claim falsifiable**, so a result where
D fails to beat E is a real finding and should be reported as one.

E's sample count and aggregation rule are set in ADR 0011. Its confidence is
its judge's, as for B, not the samples' agreement: the presenter argues for the
proposition in every sample, so the samples have nothing to disagree about
(ADR 0011, amended after the scored run). The vote is stored as a diagnostic.

---

## Ground truth

Adjudicated cases where a tribunal's holding supplies the answer.
Fixtures in `evaluation/cases/`.

The system sees `question` and `facts`. It never sees `holding`, `outcome`, or
`key_reasoning`.

Two ways this goes wrong:

**Leaking the answer into the facts.** State facts as the tribunal *found* them,
not as it *characterised* them. "The attacks struck civilians queuing for water"
is a fact. "The attacks were indiscriminate" is the holding wearing a fact's
clothes.

**Leaving out the facts the reasoning stands on.** The facts must include every
factual finding the tribunal's `key_reasoning` relies on, except the one the
question asks about. If the tribunal inferred a purpose from a campaign's lack
of military significance, the facts state that lack; they do not state the
purpose. A record thinner than the tribunal's invites the debate to find a
"gap" that the tribunal never had, and the council's attackers will find it
(the Galić rehearsals, `tuning/LOG.md`). Take additions from the case file
itself, never from memory of the case.

**Only picking easy cases.** A set of settled questions makes every arm look
equally good and measures nothing. `difficulty: contested` cases are where
calibration separates the arms, and they should be a substantial share.

If the judgment is in the corpus, set `source_case_id` — the harness excludes it
from retrieval so the system cannot read the answer back.

### The dev / held-out split

`cases/dev/` is what prompts are tuned against. `cases/held_out/` is scored
**once**, at the end.

Tuning against the test set produces a system that looks good and generalises to
nothing. Keep the split.

**The scored run has no held-out set.** It used the three core dev cases and
one stretch case, Mrkšić (ADR 0012), all seen during prompt tuning. The
write-up, `evaluation/reports/write-up.md`, says so; nothing in it measures
generalisation.

---

## Metrics

### 1. Outcome agreement

Did the system reach the tribunal's conclusion? Ternary — affirmed / rejected /
indeterminate. The headline number, and trivially scorable.

### 2. Calibration — the important one

`evaluation/metrics/calibration.py`

| Metric | Meaning |
| --- | --- |
| **Brier score** | Mean squared error of confidence vs outcome. Lower better; 0.25 = always answering 0.5 |
| **ECE** | Bucketed gap between confidence and accuracy. Lower better |
| **Overconfidence** | `mean_confidence − accuracy`. Positive = claiming more certainty than earned |

Overconfidence is the number that most directly tests the project's argument. A
system at 70% accuracy reporting 95% confidence is the failure mode the whole
design exists to fix.

With a small case set most ECE buckets will be sparse — report it alongside the
Brier score, not instead of it.

### 3. Citation validity

`evaluation/metrics/citations.py` — fully automatic, no human grading.

| Metric | Meaning |
| --- | --- |
| **Validity rate** | Share of citations that resolved cleanly |
| **Fabrication rate** | Share that pointed at an indexed instrument but did not exist there (`unresolved`) |
| **Misquote rate** | Share whose locator exists but whose quoted words did not match it (`misquoted`) |

`out_of_corpus` is excluded from both rates' denominators. Citing real authority
we have not indexed is not fabrication, and conflating them makes the number
meaningless.

`misquoted` is reported apart from fabrication, not inside it. A locator either
exists or it does not; that is an exact lookup. The quote check is a loose
token-overlap heuristic (ADR 0004): it flags a verbatim quote whose punctuation
differs from the source, and it passes a quote that drops a "not". Folding it
into the headline would put that noise into the number the project is judged on.
A misquote still lowers the validity rate, since only `resolved` counts as valid.

Expect arm A (no retrieval) to fabricate most. If it does not, that is a finding
worth investigating rather than celebrating.

### 4. Attacker independence

`evaluation/metrics/independence.py` — promised explicitly in the project brief.

| Metric | Meaning |
| --- | --- |
| **Jaccard** | Token overlap between the two attackers' objection grounds |
| **Target overlap** | Share of arguments both chose to challenge |

High Jaccard means the mandate split is not working and the second model is not
earning its place. **That is a legitimate result and should be reported as one.**
It is also the most likely place for the design to be wrong, which makes honesty
here the most valuable thing in the evaluation.

Target overlap alone is not damning — a weak argument invites challenge from
both angles. High Jaccard *and* high target overlap together is the bad signal.

### 5. Reasoning overlap (soft)

`evaluation/metrics/reasoning_overlap.py`. Scored by hand, read by the report.

Did the run rest on the grounds the tribunal actually relied on
(`key_reasoning`)? Outcome agreement alone rewards the right answer for the
wrong reasons. This is the soft metric and the report says so.

**Scored by hand, not by a model.** A model scoring the reasoning of models
puts the thing under test inside its own measurement. The usual remedy is to
validate the model judge against a hand-scored subset, but at three cases
(15 runs) that subset would be the whole set (GitHub #27).

**What to read.** The run's final position in its result file
(`data/eval/<arm>/<case>.json`): the verdict's `reasoning`, and the arguments
it kept (`verdict.surviving_argument_ids`, matched against `arguments`). For
arm E, the aggregated `arguments` and the verdict. Not objections, not
arguments the judge dropped: the question is what the conclusion rested on, not
what was said along the way.

**The scale, per `key_reasoning` point:**

| Points | Meaning |
| ---: | --- |
| **2** | The run relies on this ground, on the same legal basis the tribunal used (the provision or doctrine), or one plainly equivalent |
| **1** | The ground is there, but only partly: mentioned without being relied on, reached on a different legal basis, or missing an element the tribunal needed |
| **0** | Absent, or the run contradicts it |

A run's score is its points over the maximum, `sum / (2 × points)`, so 0.0 to
1.0 whatever the case's number of points. The arm's figure is the mean over
its scored runs, shown with how many of its completed runs that is. An unscored
run is left out, never counted as zero.

Not scored here: whether citations resolve (that is the fabrication rate),
wording, and the outcome. A run that reaches the wrong outcome can still score
points, and that is part of what the metric is for.

**Process.**

- Score from the stored results, after the scored run (#26). Nothing is re-run.
- Where practical, score without knowing the arm. Arm names are in the file
  path and the `arm` field, so have someone else hand over the runs relabelled.
- Two scorers, independently, neither seeing the other's scores. The report
  averages them per run and prints their exact agreement (points given the same
  value / points compared). It does not reconcile disagreements, and an
  agreement figure from one scorer does not exist.
- Write a note for every 1. It is the judgement call, and the note is how
  someone else checks it.

**Recording.** `evaluation/scores/reasoning_overlap.json`, committed, since
it is hand-made and cannot be regenerated:

```json
{
  "rubric_version": 1,
  "scores": [
    {
      "case_id": "icty_galic_terror",
      "arm": "full_council",
      "run_id": "eval_…",
      "scorer": "s1",
      "points": [2, 1, 0, 2],
      "notes": "point 2: …"
    }
  ]
}
```

- `points` has one entry per `key_reasoning` item, in the case file's order.
  The report refuses a wrong count, an unknown case, or a run scored twice by
  one scorer.
- A score is keyed by `run_id`. Re-running a case makes a new run, which shows
  as unscored; the old score is listed as matching nothing rather than applied
  to a run nobody read.
- `scorer` is a short label, and it is public.
- `rubric_version` is checked. Changing what a point means is a new version,
  and scores under the old one are refused rather than mixed in.

### 6. Objection severity

`evaluation/metrics/report.py` — automatic, read from stored results.

`Objection.severity` (`fatal`, `material`, `minor`) is the attacker's own rating
of its objection. The report counts, per arm, the objections the judge
**sustained** and **overruled** at each step.

| Column | Meaning |
| --- | --- |
| **Fatal / Material / Minor** | `sustained / overruled` counts at that severity |
| **Not stated** | Severity was `None` or absent. Counted apart, never as `minor`: every run recorded before the field existed lands here |
| **Overruled fatal** | The most informative dissent-log entry: the attacker said the argument fails, and the judge ruled otherwise |

Counts, not a weighted score. Weights would be invented, and three named steps
were chosen precisely to avoid inventing precision. Partial and unaddressed
rulings are not counted. The rating is self-reported, so compare arms on it
cautiously: a more severe attacker prompt raises the counts without changing
the argument.

---

## Statistical honesty

Even at 40–80 cases, differences between arms C and D carry **wide confidence
intervals**. The case set is twenty (ADR 0012, amended), so once all twenty are
run the report prints intervals, and they will be wide; a gap with overlapping
intervals is not a result. With the three cases actually scored there is no
meaningful interval at all: three cases have 10 distinct bootstrap resamples, so
a percentile interval over them describes the resampling, not the uncertainty.

So the report prints intervals only for an arm with at least 10 completed cases
(`MIN_CASES_FOR_INTERVALS` in `metrics/report.py`). The cut-off is a choice,
stated in the report's header: at 10 cases there are 92,378 distinct resamples.
Below it, each metric is a point value with its `n`, and a note says the rows
support no claim of a difference between arms.

- With enough cases, report bootstrap CIs, not bare means
- A three-point gap with overlapping intervals is not a result
- Say the sample size in every table

Overselling a small difference is the fastest way to lose credibility on a
project whose entire premise is that overconfidence is dangerous.

---

## Running it

```bash
make eval ARGS="--case icty_galic_terror"   # all five arms on one core case
make eval ARGS="--tier stretch --case icty_martic_zagreb"   # a stretch case
make eval ARGS="--tier all --case hyp_pow_militia"          # any of the twenty
make eval-arm ARM=full_council  # one arm over the core tier
make eval-report                # rebuild the report from existing results
```

Slow and quota-consuming. Never part of CI.

**The settings are frozen for the scored run.** `make eval-freeze` records
the roster, the prompt set, the embedding model and the citation index in
`evaluation/frozen-settings.json`, committed on 2026-11-16 (fingerprint
`df941348ab17`). A live run on a
machine that differs refuses to start, naming each difference
(`--allow-unfrozen-settings` overrides it for an experiment that won't be
scored), and `make eval-settings` shows the comparison. The scored run can then
be split across several people's machines, and their results pooled. Step by
step: [runbook-evaluation.md](runbook-evaluation.md).

**Run from the repo root**, as the `make` targets do. On the host the harness
finds `data/` and `prompts/` relative to the working directory. From anywhere
else it finds no citation index, so a live run refuses to start rather than
score every citation `out_of_corpus`.

**Qdrant on the host.** `.env` gives Qdrant's address inside the compose
network (`http://qdrant:6333`), which the host cannot resolve. The harness
replaces that address, and the app's identical default, with
`http://localhost:6333`, where the dev stack publishes Qdrant; any other
`QDRANT_URL` is left alone. Without this, arms B–E fail at retrieval while arm
A, which retrieves nothing, succeeds.

**Each case has 900 seconds** (`--case-timeout` overrides it). The rehearsal
(#25) measured the free judge at 120–138 s per call: arms C and D took about
270 s, and arm E, whose samples run one after another with retry backoff,
passed the old 300 s limit. A case that times out has still spent its judge
calls, so a tight limit wastes quota; `--resume` re-runs only timed-out and
failed cases.

**`--dry-run` makes no model calls in any arm.** Presenter, attackers and judge
are all mocked, and so is arm E's sampling. It checks that the harness, the
result files and the report work end to end, and costs no quota. Its results
are marked synthetic and the report keeps them apart from real ones.

**Budget:** one case through all five arms is up to 7 judge calls (A 1, B 1,
C 2, D 2, E 1). The judge's free tier is 50 requests/day across the OpenRouter
account, and the harness caps itself at 40. Before a live run it reserves three
attempts per expected call, 21 for one case, and refuses to start if that would
pass the cap. So run **one case per invocation**: about two cases a day, the
core three over two days, stretch cases with what is left. A local judge for
iteration costs no quota but changes the result, so the report records which
backend ran.

Arm E will not add judge calls in proportion to its sample count: it aggregates
*n* presenter samples and judges once, so its cost sits close to arm B's. Its
*n* is set by D's call count, not the other way round.

**Time:** about 15 minutes per case through all five arms. Measured on the
rehearsal (GitHub #25): `icty_galic_terror`, full corpus, the free-tier roster in
`.env`, wall-clock seconds per arm.

| Arm | Model calls | Run 1 | Run 2 | Run 7 (unattended) |
| --- | ---: | ---: | ---: | ---: |
| A raw | 2 | 36 | 29 | 19 |
| B rag | 2 | 40 | 46 | 60 |
| C single_attacker | 6 | 274 | 149 | 124 |
| D full_council | 8 | 268 | 332 | 134 |
| E self_consistency | 8 | 290 | 350 | 407 |
| **All five** | 26 | **908** (15.1 min) | **907** (15.1 min) | **744** (12.4 min) |

Run 1's arm E is its re-run at 900 s; the first attempt timed out at the old 300 s
default. Run 2's arm E is also a re-run, after the judge returned JSON missing
`reasoning` and `confidence` twice; the time shown is the run that completed.
Run 7 is the first to complete all five arms with no re-run, on the frozen
settings (`tuning/LOG.md`).

Where the time goes:

- **The judge dominates.** Each call took 27-188 s
  (`openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`), against 2-9 s for a
  presenter or attacker call on Groq. C and D make two judge calls each, so they
  vary most: arm C took 274 s in one run and 149 s in the other.
- **Arm E is sequential.** Its 7 presenter samples run one after another, and
  Groq's rate limit makes the client back off between them: 33 requests for 7
  replies in run 2, about 40 s per sample.
- **Three arm runs passed 300 s** across the two rehearsals: D at 332 s, and E at
  308 s (the attempt that failed) and 350 s. A day that is slower again can still
  exceed 900 s, and a timed-out case is recorded, not scored.

So the three core cases take about 45 minutes of wall-clock time, in addition to
the quota limit of about two cases a day.

Results land in `data/eval/`, reports in `evaluation/reports/`.

---

## Reporting

`make eval-report` writes `evaluation/reports/evaluation-report.md` from the
stored results in `data/eval/`. Nothing is re-run. It has two tables.

**The scored run's report is committed; don't overwrite it from `data/eval/`.**
`evaluation/reports/evaluation-report.md` is the three core cases, and
`evaluation-report-with-stretch.md` adds Mrkšić. Both are built from the 20
results in `evaluation/results/scored-run/`, which are the run's result files
with the corpus text removed (`python -m harness.artifacts export`; the repo is
public, ADR 0014). `evaluation/reports/write-up.md` reads them, states the
limits, and shows how to rebuild either report.

**Per arm:** accuracy, Brier, ECE, overconfidence, fabrication rate, misquote
rate, attacker independence and reasoning overlap, each with its `n`. Bootstrap intervals are
shown only from 10 completed cases (see *Statistical honesty*). Arms are listed
in ladder order, A to E.

**Per case:** one row for each case and arm, giving the tribunal's outcome, the
arm's prediction, whether it matched, the judge's confidence, and the citation
counts (unresolved, misquoted, and the eligible total they are out of), and the
run's reasoning overlap where it has been scored. At three
cases this table is the result: it shows which arm got which case wrong, which
the averages hide. A run that errored or timed out is marked as such, not
scored.

The header also lists the roster, prompt set and embedding model the results
ran under. Results that differ in any of them are refused unless the report is
run with `--allow-mixed-settings`, which names each variant and labels each
per-case row with it: two rosters mean the arms differ by model as well as by
structure (ADR 0009).

The header names the citation index that scored the results (its hash prefix,
instrument and locator counts). Results scored against different indexes, or
written before results recorded one, are refused unless the report is run with
`--allow-mixed-corpora`, which labels each per-case row with its index.
Citation statuses from two indexes are not comparable: the same citation can be
`resolved` on one machine and `out_of_corpus` on another.

Attacker independence is measured only where both attackers objected. Arm C has
one attacker, so it shows none; in a D run where one attacker raised nothing it
is blank too.

Not yet in the report: mean rounds, mean tokens, and a breakdown by
`difficulty`. That breakdown is the one that matters. The interesting question
is not whether the council wins on average; it is whether it wins **on contested questions**,
which is what it was designed for and where a single pass is most dangerous.

Report negative results. If two attackers do not beat one, that is a finding
about mandate separation, and it is more useful than a flattering number.
