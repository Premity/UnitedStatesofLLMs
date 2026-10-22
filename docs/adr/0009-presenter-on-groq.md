# 0009 — The presenter runs on Groq, not Mistral

**Status:** Proposed
**Date:** 2026-10-22

## Context

The presenter was specified as Mistral Magistral — a reasoning-tuned model,
chosen partly because legal argument is the one role where chain-of-thought
quality is visible in the output.

During first light (T0) it never ran. Mistral returned 429 on the *first*
request from a freshly created free-tier account, not after a burst. Whatever
the cause, a backend that rejects the opening request is not a backend a
four-person team can develop against for three weeks.

This is not purely an operational swap. The model roster is a **claim this
project makes**, not an implementation detail. The literature review identifies
"adversarial scrutiny is simulated — all agents are one model" as a gap, and the
stated response is that the four roles run on four different model families, so
disagreement is a property of the models rather than of sampling temperature.
Changing a role's family changes what the evaluation is evidence for, and
`attacker_independence` is measured on exactly that premise.

Two further pressures made the choice urgent rather than deferrable:

- **The roster drifted.** During T0 one machine ran
  `groq/llama-3.3-70b-versatile` and another `groq/openai/gpt-oss-120b`. Those
  are different families. Results produced on the two are not comparable, and
  nothing in the repo said which was canonical.
- **The scored run cannot absorb a mid-run change.** It occupies days 14–19
  against a 100-request/day judge quota. A presenter swap partway through
  produces a dataset with no single system under test.

## Decision

The presenter runs on **`groq/openai/gpt-oss-120b`**, pinned as the default in
`.env.example`, `docker-compose.yml` and `RoleModels`.

One id, not a family. `groq/llama-3.3-70b-versatile` is a fallback if Groq
retires or rate-limits this model, and switching is a config change (ADR 0002) —
but it is a **deliberate** switch that gets recorded here and in the report, not
a per-machine default.

The four-family property is preserved: presenter (OpenAI OSS, via Groq),
doctrinal attacker (Qwen), evidentiary attacker (Gemma), judge (Gemini). No two
roles share a base model.

Every result carries the model that produced it. `ModelConfig.model_id` is
already written into each turn of the run artifact, so this is a reporting
obligation rather than new machinery: **the report must state the roster, and
any run whose roster differs is reported separately or discarded.**

## Consequences

**Gained:**

- A presenter that answers. Development is not blocked on one provider's
  free-tier behaviour.
- An unambiguous roster. "Which presenter?" has one answer, in the repo.
- Family diversity is intact, so the independence argument still holds.

**Given up:**

- **Magistral's reasoning tuning.** It was picked for a reason and the
  replacement is a general instruction-tuned model. If presenter arguments are
  visibly thinner — fewer articulated steps, weaker citation selection — that is
  a plausible cause and worth testing before blaming prompts.
- **A free-tier dependency, relocated not removed.** Groq's limits are
  generous for development and still a limit. If Groq rate-limits during the
  scored run, the fallback is a change to the system under test mid-dataset.
  Rehearsal (T4-4) should run enough presenter calls to find this on day 11
  rather than day 16.
- **One more thing the report must disclose.** The design documents name
  Mistral Magistral; the limitations section must say the presenter is
  `gpt-oss-120b` and why.

**What would make us revisit this:** Mistral's free tier becoming reliable and
presenter quality measurably worse on Groq — in that order. Reverting is a
config change plus an ADR superseding this one, and it must not happen between
the start of the scored run and the end of it.

**Constraint this creates:** the roster is frozen from the start of the scored
run (day 14) until it completes. A roster change after that point invalidates
every case already scored, because the arms would then differ by model as well
as by structure — which is precisely the confound arm E exists to remove.
