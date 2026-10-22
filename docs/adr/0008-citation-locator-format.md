# 0008 — One citation locator format, with sub-paragraphs inside the article

**Status:** Proposed
**Date:** 2026-10-21

## Context

Every citation a model produces is checked by looking up its **locator** — a
short string such as `ap_i/art.51(2)` — in the citation index (see
[ADR 0004](0004-citation-integrity.md)). The same string is produced in code by
`Citation.locator()`, used as a key in `data/index/citation_index.json`, and
written into every stored run artifact.

The format is already in use but has never been written down, and treaty
citations invite variation. The same provision can plausibly be written
`ap_i/art.51(2)`, `ap_i/art.51.2`, `ap_i/art.51/para.2`, or with a separate
paragraph field. Any two of those disagreeing is a lookup miss, and a lookup
miss on an indexed instrument is not a harmless error here: it comes back as
`unresolved`. That is the status ADR 0004 reserves for fabrication, and it feeds
`fabrication_rate` directly. A formatting inconsistency would show up in the
evaluation as the model inventing law.

## Decision

There is **one locator format**:

| Source | Pattern | Example |
| --- | --- | --- |
| Treaty article | `<instrument>/art.<article>` | `ap_i/art.51` |
| Treaty paragraph or sub-paragraph | `<instrument>/art.<article>(<para>)(<sub>)…` | `ap_i/art.51(2)`, `rome_statute/art.8(2)(b)(i)` |
| Jurisprudence paragraph | `<case_id>/para.<n>` | `icty_galic_tj/para.58` |

**Sub-paragraphs go inside the article string**, in parentheses, outermost
first. In code that is `article="51(2)"` — there is no separate paragraph field.

Instrument and case ids are the stable ids from the corpus manifests
([ADR 0007](0007-curated-corpus.md)): lowercase `snake_case`, no spaces.

A whole article and each of its paragraphs are **distinct locators**.
`ap_i/art.51` does not resolve `ap_i/art.51(2)`, or the reverse.

The format is pinned by `test_locator_formats_are_stable`, which now includes a
sub-paragraph case. Changing it requires a new ADR that supersedes this one.

## Consequences

**Gained:**

- One unambiguous key per provision, shared by code, the index, and run
  artifacts
- Pinpoint citation: a model can cite the exact paragraph it relies on, and the
  judge can check that paragraph rather than a whole article
- No schema change: the format is what `Citation.locator()` already produces

**Given up:**

- Index size. Because articles and paragraphs are separate keys, the index needs
  an entry for every form the models actually cite, not just one per article.
- No fallback. A citation to `art.51(3)` does not fall back to `art.51`. That
  keeps resolution strict, but it means a gap in the index is indistinguishable
  from a fabrication.
- Text duplication. A whole-article entry must carry the full article text and
  each paragraph entry its own paragraph, because `misquoted` checks quoted
  words against whichever entry the locator resolves to.

**Constraint this creates:** once an instrument is listed in the index's
`instruments` array, every provision of it that models might cite must be
present in `entries`. A listed instrument with missing paragraphs will report
correct citations as `unresolved` and inflate `fabrication_rate`. While the T0
index is a hand-built stub, a cluster of `unresolved` citations to a listed
instrument is a coverage gap to check before it is read as model fabrication.
Entry text must be copied exactly from the source, or correct quotations will
be reported as `misquoted`.

As with manifest ids (ADR 0007), locators are written into stored runs, so the
format is effectively permanent: changing it retroactively breaks the citation
resolution of every past run.
