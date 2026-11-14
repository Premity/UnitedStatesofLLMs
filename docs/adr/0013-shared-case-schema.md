# 0013 — The case schema lives in `council-core`; the API serves only its public fields

**Status:** Accepted
**Date:** 2026-11-15

## Context

`evaluation/cases/dev/*.json` holds prepared cases, but the question form cannot
load one, so every demo question is typed by hand (GitHub #17). A picker needs
the API to serve cases, and two constraints decide how.

- **A case file contains the ground truth.** `holding`, `outcome` and
  `key_reasoning` must never reach the browser, or the demo shows the answer
  beside the question.
- **`runtime/api` does not depend on `evaluation`.** Both depend only on
  `council-core`. The schema, `EvaluationCase`, was defined inside
  `evaluation/harness/cases.py`, so the API could parse a case file only by
  inverting that arrow or by writing a second copy of the schema.

## Decision

**Move the schema into `council-core`** as `council_core.models.case.Case` (with
`Outcome`). Both services already stand on `council-core`, so no new dependency
is created and the arrow still points one way.

**Strip ground truth in one place.** `Case.public()` returns a `PublicCase` —
`id`, `title`, `court`, `year`, `question`, `facts`, `difficulty` and nothing
else. It is a separate model rather than a filtered dump of `Case`, so a field
added to `Case` later is excluded by default and has to be added to
`PublicCase` on purpose to reach the browser.

**The files stay where they are.** The API reads `evaluation/cases/dev/*.json`
by path (`CASES_DIR`, mounted read-only into the container). That is a
filesystem location, not a Python import. The evaluation harness keeps its
loaders and the `CORE`/`STRETCH` tiers, which are scope decisions about the
scored run, not part of the schema.

Only `dev/` is served. `held_out/` is scored once and never looked at while
iterating; serving it to a picker would put it in front of people tuning
prompts.

## Consequences

**Gained:** one schema, one stripping function, no copy to drift. A test fails
if any ground-truth field reaches a response, including one added to `Case`
later.

**Given up:**

- A model rename. `EvaluationCase` became `Case`, which touched the harness and
  its tests.
- The API now needs the case files at runtime, so compose mounts
  `evaluation/cases` into the api container. A deployment that omits the mount
  serves an empty list rather than failing.

**What would make us revisit this:** a held-out or hosted-demo case set that is
not a directory of JSON files, which would want a real store behind the same
`PublicCase`.
