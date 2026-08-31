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

Four arms, each differing from the one above in exactly one respect. Defined in
`evaluation/harness/arms.py`.

| Arm | Configuration | Isolates |
| --- | --- | --- |
| **A** `raw` | Single pass, no retrieval | The raw baseline |
| **B** `rag` | Single pass + retrieval | What grounding alone contributes |
| **C** `single_attacker` | Presenter + doctrinal attacker + judge | What adversarial challenge contributes |
| **D** `full_council` | Both attackers | Whether the second attacker earns its place |

B exists so the council is not credited for gains that retrieval alone produces.
Without it, "our system beats a raw LLM" is an uninteresting claim.

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
| **Fabrication rate** | Share that pointed at an indexed instrument but did not exist there |

`out_of_corpus` is excluded from the fabrication rate. Citing real authority we
have not indexed is not fabrication, and conflating them makes the number
meaningless.

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

Did the system anticipate the grounds the tribunal actually relied on
(`key_reasoning`)? Needs a rubric or an LLM judge. Report it, and be honest that
it is the soft metric.

---

## Statistical honesty

With 40–80 cases, differences between arms C and D carry **wide confidence
intervals**.

- Report bootstrap CIs (`bootstrap_ci` in `calibration.py`), not bare means
- A three-point gap with overlapping intervals is not a result
- Say the sample size in every table

Overselling a small difference is the fastest way to lose credibility on a
project whose entire premise is that overconfidence is dangerous.

---

## Running it

```bash
make eval                       # all four arms
make eval-arm ARM=full_council  # one arm
make eval-report                # rebuild the report from existing results
```

Slow and quota-consuming. Never part of CI.

**Budget:** with 60 cases × 4 arms, arms C and D use several judge calls each.
Gemini AI Studio's free tier is 100 requests/day, so a full run spans multiple
days — or point the judge at a local model for iteration and use the API model
only for the final scored run. Record which, because it changes the result.

Results land in `data/eval/`, reports in `evaluation/reports/`.

---

## Reporting

For each arm: outcome agreement, Brier, ECE, overconfidence, citation validity,
fabrication rate, mean rounds, mean tokens — each with a bootstrap CI and an
explicit `n`.

Then break results down by `difficulty`. The interesting question is not whether
the council wins on average; it is whether it wins **on contested questions**,
which is what it was designed for and where a single pass is most dangerous.

Report negative results. If two attackers do not beat one, that is a finding
about mandate separation, and it is more useful than a flattering number.
