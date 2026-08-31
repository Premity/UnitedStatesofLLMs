# Corpus

What the system retrieves over, how it is scoped, and the rules that make
citation validation possible.

---

## Tiering

The corpus is **curated, not comprehensive**. See
[ADR 0007](adr/0007-curated-corpus.md) for why.

| Tier | Content | Location | Committed? |
| --- | --- | --- | --- |
| **1** | Treaty text, customary IHL rules, UN resolutions | `corpus/` | Yes — small, canonical, worth diffing |
| **2** | Curated jurisprudence | `data/cache/` | No — fetched from manifest |
| **3** | Everything else | Not ingested | Cited → `out_of_corpus` |

Tier 3 is a feature. A citation to unindexed authority is marked visibly
unverifiable rather than silently accepted, and stays distinct from `unresolved`
— the fabrication signal.

---

## Manifests define the scope

`corpus/manifests/` holds three files. The fetcher downloads **exactly** what
they list and never crawls, so every change to the corpus is a reviewable diff.

| Manifest | Tier | Contents |
| --- | --- | --- |
| `treaties.json` | 1 | Geneva Conventions I–IV, AP I–II, Rome Statute, Hague IV |
| `cases.json` | 2 | Curated ICC / ICJ / ICTY / ICTR jurisprudence |
| `resolutions.json` | 1 | UNGA resolutions bearing on IHL |

### Adding a case

1. Add an entry with `id`, `court`, `year`, `url`, and `relevance` — say which
   evaluation question or demo scenario it earns its place against
2. `make fetch` then `make index`

> **The `id` is a permanent identifier.** Models cite `icty_galic_tj/para.58`,
> and that locator is written into every stored run artifact. Renaming an id
> retroactively breaks citation resolution for every past run.

---

## Document shape

Every source normalises to this, regardless of where it came from:

```json
{
  "id": "rome_statute",
  "type": "treaty",
  "title": "Rome Statute of the International Criminal Court",
  "year": 1998,
  "source_url": "https://www.icc-cpi.int/...",
  "spans": [
    {
      "locator": "rome_statute/art.8(2)(b)(iv)",
      "article": "8(2)(b)(iv)",
      "text": "Intentionally launching an attack in the knowledge that…",
      "parent": "rome_statute/art.8"
    }
  ]
}
```

For judgments, spans are numbered paragraphs:

```json
{
  "id": "icty_galic_tj",
  "type": "case",
  "court": "ICTY",
  "spans": [
    {
      "locator": "icty_galic_tj/para.58",
      "paragraph": "58",
      "text": "The Trial Chamber finds that…",
      "section": "III. Findings"
    }
  ]
}
```

**`locator` is the join key.** It is what the citation index maps, what models
emit, and what the resolver looks up.

---

## Chunking is a correctness requirement

Not a tuning knob.

| Source | Chunk unit | Why |
| --- | --- | --- |
| Treaty | One article or subparagraph | `8(2)(b)(iv)` is how it is cited |
| Judgment | One numbered paragraph | `para. 58` is how it is cited |
| Customary IHL | One rule | `Rule 14` is how it is cited |
| Resolution | One operative paragraph | How it is cited |

Chunking by token window would make `icty_galic_tj/para.58` unresolvable, and
the whole citation-validation mechanism would collapse. Whatever else changes
about chunking, granularity must stay at citation level.

Two consequences worth planning for:

- **Very short spans.** Some treaty articles are one line. Give the embedder the
  parent article as context via the `parent` field rather than merging spans.
- **Very long spans.** Some judgment paragraphs run pages. Sub-chunk them for
  embedding, but keep the paragraph locator on every sub-chunk so citations
  still resolve.

---

## What the indexer produces

### 1. The Qdrant collection

Collection `ihl_corpus`, embedded with BGE-M3 via fastembed. Payload per point:

```json
{
  "citation_type": "treaty",
  "instrument": "rome_statute",
  "article": "8(2)(b)(iv)",
  "case_id": null,
  "paragraph": null,
  "rule_number": null,
  "text": "Intentionally launching an attack…",
  "source_url": "https://www.icc-cpi.int/..."
}
```

### 2. The citation index

`data/index/citation_index.json` — what the resolver reads:

```json
{
  "version": "0.1.0",
  "instruments": ["rome_statute", "gc_iv", "icty_galic_tj"],
  "entries": {
    "rome_statute/art.8(2)(b)(iv)": {
      "text": "Intentionally launching an attack…",
      "source_url": "https://www.icc-cpi.int/..."
    }
  }
}
```

Both fields matter. `entries` resolves locators; `instruments` is what
distinguishes `unresolved` (indexed instrument, missing locator — the
fabrication signal) from `out_of_corpus` (never indexed). Without the
`instruments` list every miss looks like fabrication and the metric is worthless.

---

## Sources

| Source | Covers | Notes |
| --- | --- | --- |
| [ICRC IHL Databases](https://ihl-databases.icrc.org/) | Treaties, customary IHL | Structured, stable, article-addressable |
| [ICC](https://www.icc-cpi.int/) | ICC judgments | PDFs; paragraph numbers in the text |
| [ICTY](https://www.icty.org/) | ICTY judgments | PDFs; large |
| [ICJ](https://www.icj-cij.org/) | ICJ cases and advisory opinions | PDFs; huge — curation matters most here |
| [UN Digital Library](https://digitallibrary.un.org/) | Resolutions | Multiple formats |

Be polite: rate-limit, cache aggressively, identify the client in a User-Agent.
These are public institutional archives.

---

## Current status

Both pipeline stages are **scaffolded but not implemented**. Structure, CLI, and
output contracts are settled; the parsers are not written. See
[ISSUES.md](../ISSUES.md) for what remains.
