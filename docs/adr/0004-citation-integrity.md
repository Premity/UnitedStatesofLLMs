# 0004 — Citation validation as first-class machinery

**Status:** Accepted
**Date:** 2026-08-31

## Context

The project's abstract claims that retrieval grounding prevents "drift into
fabricated authority, a known failure mode of legal LLMs."

Fabricated citations are the most documented failure of language models in legal
work — the kind that has produced actual court sanctions. A model writes
*"as held in Prosecutor v. Galić at para. 58"* and it is fluent, correctly
formatted, and entirely invented.

A prompt instruction saying "only cite real sources" does not fix this. Models
comply with the *form* of the instruction while still producing plausible
locators, because plausible locators are exactly what the training distribution
rewards.

## Decision

Citations are **structured data validated by machinery**, not prose taken on
trust.

1. Models emit citations as objects with typed locator fields — instrument,
   article, case id, paragraph — never as free text.
2. Every citation is resolved against a corpus index built by the indexer at
   `data/index/citation_index.json`.
3. Resolution happens at the role boundary (`BaseRole.ground_arguments`), so no
   downstream code has to remember to do it. Arguments reach the judge already
   marked grounded or unsupported.
4. The judge is shown each citation's status and told to treat unsupported
   claims accordingly.
5. The frontend and the exported dissent log **display failures rather than
   hiding them**.

Four outcomes, deliberately distinguished:

| Status | Meaning |
| --- | --- |
| `resolved` | The locator exists; text attached |
| `unresolved` | Instrument is indexed, nothing at that locator — **the fabrication signal** |
| `out_of_corpus` | Real authority we have not indexed — unverifiable, not fabricated |
| `misquoted` | Locator resolves but the quoted words are not in it |

## Consequences

**Gained:**

- Fabrication becomes *measurable*. `citation_validity_rate` and
  `fabrication_rate` are fully automatic metrics, needing no human grading, and
  they measure precisely the failure mode the project names.
- The check cannot be talked past. It never reads the model's prose, only its
  structured locator.
- A reader of the dissent log can see where a model reached for authority that
  does not exist.

**Given up:**

- Models must emit structured output, which small local models do imperfectly —
  hence the repair retry in `complete_structured`.
- Only *existence* is checked, not *relevance*. A citation can resolve
  cleanly and still be applied to a proposition it does not support. Catching
  that needs semantic verification, which is future work.
- Quote matching is loose (token overlap ≥ 0.6). It catches text that is not
  there at all, not paraphrase or elision. Tightening it would produce false
  positives on normal model behaviour.

**Why `unresolved` and `out_of_corpus` must stay separate:** merging them would
penalise a model for citing real authority our small corpus happens not to
index, making the fabrication rate meaningless. This distinction is load-bearing
for the evaluation and must survive refactoring.
