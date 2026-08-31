# 0007 — Curated corpus scoped by manifest, not a crawl

**Status:** Accepted
**Date:** 2026-08-31

## Context

The system needs to retrieve over treaty text and jurisprudence. The instinct is
to ingest everything available: all of the ICJ's documents, the full ICTY and
ICTR archives, every ICC filing.

That instinct is wrong here, for three reasons.

**Scale.** ICJ and ICTY archives run to hundreds of thousands of pages. Fetching
and embedding them would take days and produce tens of gigabytes.

**Retrieval quality.** A proportionality question does not benefit from having
12,000 pages of maritime delimitation in the index. More irrelevant material
means worse top-k results, not better ones.

**Nothing needs it.** The evaluation is scoped to a few dozen adjudicated cases
and the demo to a handful of scenarios. Corpus coverage beyond that is unused.

## Decision

The corpus is defined by **committed manifests** under `corpus/manifests/`. The
fetcher downloads what they list and nothing else. It never crawls.

Three tiers:

| Tier | What | Where |
| --- | --- | --- |
| 1 | Treaty text, customary IHL rules, UN resolutions — small, canonical, stable | Committed to the repo |
| 2 | Curated jurisprudence — the cases that matter for evaluation and demo | Fetched into gitignored `data/cache/` |
| 3 | Everything else | Not ingested; citations to it resolve as `out_of_corpus` |

## Consequences

**Gained:**

- Corpus scope is a reviewable diff. Adding a case is a manifest PR.
- Fetching finishes in minutes rather than days
- Retrieval quality is higher, because the index contains only relevant material
- Tier 1 gets version history on the project's source of truth, which is worth
  the few megabytes

**Given up:**

- Coverage. Many real questions touch authority we have not indexed.
- Case selection is a human judgement, and a biased selection would bias the
  evaluation. Mitigated by choosing cases for the legal questions they settle,
  not for what the system gets right.

**Why Tier 3 is a feature, not a gap:** a citation to unindexed authority
resolves as `out_of_corpus` — visibly unverifiable rather than silently
accepted. Kept distinct from `unresolved`, which is the fabrication signal. See
[ADR 0004](0004-citation-integrity.md).

**Constraint this creates:** citation ids in the manifests are **stable
identifiers**. Models cite `icty_galic_tj/para.58`, and that locator is written
into every stored run artifact. Renaming an id retroactively breaks the citation
resolution of every past run.
