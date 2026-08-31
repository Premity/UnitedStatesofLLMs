# 0005 — Run artifacts as JSON files, not a database

**Status:** Accepted
**Date:** 2026-08-31

## Context

Every debate must be persisted with enough provenance to reproduce and audit it:
which models answered, at what temperature, against which prompt versions, over
which retrieved spans, and what each said. Without that the dissent log has no
provenance and the evaluation is not reproducible.

The options were a relational database (Postgres) or flat files.

## Decision

One directory per run under `data/runs/<run_id>/`:

```
artifact.json     complete record — the source of truth
dissent.md        rendered dissent log
dissent.html      print-ready version
```

## Consequences

**Gained:**

- No database service, no migrations, no ORM, no connection pooling
- The evaluation harness reads runs in bulk, which is exactly what a directory
  of JSON is good at
- A run artifact is diffable, greppable, and can be attached to a bug report or
  committed as a fixture
- The rendered exports sit beside the data they came from

**Given up:**

- No cross-run queries. Nothing at runtime needs them — the evaluation harness
  loads everything into pandas anyway.
- No concurrent-write safety. Each run writes only its own directory, so this
  does not arise.
- Listing runs is an `O(n)` directory scan. Fine at the hundreds-to-low-thousands
  scale this project will reach.

**Revisit if:** the frontend needs to search or filter across runs, or runs
reach a scale where scanning is slow. Migrating is straightforward — the
artifact is already a well-defined Pydantic schema, so it becomes a JSONB column
without reshaping anything.

**Constraint this creates:** `data/runs/` is gitignored. Anything that must
survive a clean checkout — an evaluation fixture, a demo transcript — has to be
copied somewhere committed, deliberately.
