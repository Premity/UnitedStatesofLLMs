# Evaluation cases

Adjudicated questions where a tribunal's holding is the ground truth.

## The dev / held-out split

`dev/` is what prompts are tuned against. `held_out/` is scored **once**, at the
end, and never looked at while iterating. Mixing them invalidates every number
in the report — a system tuned against its own test set will look good and
generalise to nothing.

## Writing a case

The system sees `question` and `facts`. It never sees `holding`, `outcome`, or
`key_reasoning`.

Two things go wrong most often:

1. **Leaking the answer into the facts.** State facts as the tribunal found
   them, not as the tribunal characterised them. "The attacks struck civilians
   queuing for water" is a fact. "The attacks were indiscriminate" is the
   holding wearing a fact's clothes.

2. **Picking only easy cases.** A set of settled questions makes every arm look
   equally good and measures nothing. `difficulty: contested` cases are where
   calibration separates the arms, and they should be a substantial share of the
   set.

If the judgment is in the corpus, set `source_case_id` — the harness excludes it
from retrieval so the system cannot simply read the answer back.

## Fictional cases

Cases whose id starts `hyp_` (court `Hypothetical`) are invented: made-up
states, places, people and events, with real treaty and customary law. No model
can have seen their outcomes, so they test reasoning rather than recall. Their
ground truth is **authored**, not a tribunal's, and every such `holding` begins
"Authored ground truth" (enforced by `test_case_tiers.py`). Write the facts so
the law gives a clear answer, or, for an `indeterminate` case, so the question
sits on a point the law leaves open, and say which in `key_reasoning`.
Never borrow a real conflict's names, dates or geography.

## Target size

**The scored run was three of the dev cases, with three more as a stretch;
an `extended` tier takes the set to twenty** (ADR 0012, amended; `CORE_CASE_IDS`,
`STRETCH_CASE_IDS` and `EXTENDED_CASE_IDS` in `harness/cases.py`). That is a demonstration, not a statistical comparison.

For an evaluation meant to support a claim about the arms: 40–80 cases. Below
roughly 40, bootstrap intervals are so wide that no comparison between arms will
be meaningful.
