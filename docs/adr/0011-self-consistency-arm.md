# 0011 — Self-consistency control arm (Arm E) aggregation rule and compute matching

**Status:** Accepted
**Date:** 2026-11-06

## Context

The headline claim of this project is that an adversarial multi-agent council
(Arm D) achieves superior calibration and lower citation fabrication than a
single-pass system. However, reviewer scepticism will immediately identify a
fatal compute confound: Arm D executes multiple model calls per case (presenter,
two attackers, and judge across 1–3 rounds, totaling 4–12 calls), whereas a
naive baseline (Arm B, RAG) runs only one or two calls.

If Arm D outperforms Arm B, a critic can reasonably argue: "The council did not
help; you simply bought performance by spending 6x the model compute."

To defeat this confound, the evaluation ladder includes **Arm E
(`self_consistency`)**: a compute-matched control based on self-consistency
(Wang et al., 2022). Arm E runs the presenter alone with retrieval, samples it
*n* times at a temperature that produces genuine variation, and aggregates the
samples into one answer and one confidence. The judge runs once over the
aggregated answer, mirroring Arm B's evaluation structure while matching Arm D's
total model calls on the exact same case.

Three decisions must be permanently settled before implementing Arm E:
1. What sampling temperature produces meaningful variation without schema
   breakage?
2. How is the sample count *n* derived from Arm D's call count on the same case?
3. What is the aggregation rule, and how is the aggregate confidence computed?

## Decision

### 1. Sampling temperature: $T = 0.7$

The presenter is sampled at **`temperature = 0.7`**.

At $T = 0.0$, repeated sampling collapses into greedy decoding, generating *n*
identical outputs and reducing Arm E to Arm B. At high temperatures ($T \ge 1.0$),
models frequently produce invalid JSON, hallucinated legal provisions, or
incoherent doctrinal arguments. $T = 0.7$ strikes the empirical sweet spot
established in self-consistency literature: sufficient exploration of alternative
legal characterisations while maintaining rigorous structured output and prompt
adherence.

### 2. Derivation of *n* from Arm D's call count

The sample count *n* is **derived dynamically per case from Arm D's actual call
count on that case**, not fixed globally in advance.

In Arm D, each round executes 4 model calls:
- 1 Presenter (opening or rebuttal)
- 1 Doctrinal Attacker
- 1 Evidentiary Attacker
- 1 Judge

Over $R$ rounds ($R \in \{1, 2, 3\}$), Arm D makes $C_D = 4 \times R$ model calls
(recorded as `len(state.turns)`).

In Arm E, the presenter is sampled $n$ times with retrieval grounding. The judge
then evaluates the aggregated position once ($1$ model call). To equate total
model invocations between Arm D and Arm E:

$$\text{total\_calls}(E) = n + 1$$
$$\text{total\_calls}(D) = C_D$$
$$n = \max(1, C_D - 1)$$

If Arm D terminates in round 1 ($C_D = 4$), Arm E draws $n = 3$ presenter samples
plus 1 judge call ($3 + 1 = 4$, exactly matching D). If Arm D goes 3 rounds
($C_D = 12$), Arm E draws $n = 11$ presenter samples plus 1 judge call ($11 + 1 = 12$).
In all cases, total model calls match Arm D within $\pm 1$.

If Arm E is evaluated in a judge-free ablation configuration (`has_judge = False`),
$n = \max(1, C_D)$, maintaining exact call parity.

### 3. Aggregation rule: majority vote with agreement rate as confidence

1. **Outcome majority voting:** Each presenter sample advances an outcome
   (e.g., `affirmed`, `rejected`, `indeterminate`). The aggregated outcome
   $\text{outcome}^*$ is determined by plurality/majority vote:
   $$\text{outcome}^* = \arg\max_{o} \sum_{i=1}^n \mathbb{I}(o_i = o)$$
2. **Confidence via agreement rate:** The aggregated confidence is the empirical
   agreement rate across the $n$ samples:
   $$\text{confidence} = \frac{\text{count}(\text{outcome}^*)}{n}$$
   A case where 7 of 7 samples reach `affirmed` yields 1.0 confidence (settled);
   a 4-to-3 split yields $4/7 \approx 0.57$ (contested). This directly mirrors
   human consensus calibration without relying on uncalibrated self-reported
   probabilities.
3. **Deterministic tie-breaking:** If votes tie (e.g. 2 `affirmed` vs 2 `rejected`),
   the tie is resolved by highest mean sample confidence among the tied sets; if
   confidences are equal, it resolves to `indeterminate`.
4. **Argument synthesis for the Judge:** The arguments from the winning modal
   sample (or highest-confidence sample from the majority class) are forwarded to
   the Judge. The Judge runs once to rule on surviving arguments, verify citations,
   and log overruled points.

## Consequences

**Gained:**
- **Eliminates the compute confound:** The evaluation can definitively prove
  whether multi-agent adversarial tension adds value beyond equal-compute sampling.
- **Quota efficiency:** The expensive judge model runs only once per case in
  Arm E, preserving the strict 50 request/day OpenRouter free-tier quota.
- **Natural calibration:** The agreement rate provides an empirical confidence
  estimate that can be directly compared against Arm D's judge confidence in
  Brier and ECE scores.

**Given up:**
- **Execution dependency:** Arm E cannot be run for a case until Arm D has completed
  that case, because *n* depends on D's observed round termination.
- **Single-model family limitation:** Arm E uses only the presenter model family,
  so it does not benefit from cross-family disagreement.
