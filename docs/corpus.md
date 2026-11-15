# Corpus

What the system retrieves over, how it is scoped, and the rules that make
citation validation possible.

> Building this turned up eleven problems, almost none of which raised an
> exception. If you are about to change the fetcher, the parsers or the
> embedding model, read [corpus-findings.md](corpus-findings.md) first.

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

Collection `ihl_corpus`, embedded via fastembed with `EMBEDDING_MODEL` (default
`BAAI/bge-large-en-v1.5`, 1024 dimensions; ADR 0001 says why not BGE-M3).
One point per locator. Payload per point:

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

### Sharing a built index

Embedding is the expensive stage, and a 16GB machine may not manage it. One
machine builds the index and the others import it (ADR 0014):

```bash
# On the machine that ran the indexer, with the stack up:
make export-index          # writes data/bundles/ihl-index-<hash>.tar

# On the machine receiving it, with the stack up:
make import-index FILE=ihl-index-<hash>.tar
docker compose restart api # the API loads the citation index once, at startup

# On both:
make index-status          # the Fingerprint lines must match
```

A bundle holds both halves above plus the settings they were built with, and
the tools refuse anything that would be silently wrong:

- **Export** refuses a collection whose point count differs from the citation
  index's locator count (an embedding run killed partway), or whose vector
  width is not the configured model's.
- **Import** refuses a bundle embedded with a different `EMBEDDING_MODEL`, from
  a different Qdrant version, or whose citation index does not match its
  manifest. It restores Qdrant first and writes the citation index only if
  the restore checks out, keeping the previous one as `citation_index.json.bak`.
- **Status** prints the fingerprint and flags the same mismatches, plus a
  citation index changed since the last import.

The tools read settings the way the API container does: environment first,
then `.env`. They run on the host and reach Qdrant at `localhost:6333`. The one
exception is `QDRANT_URL`: `.env` holds the in-network address
(`http://qdrant:6333`), which the host cannot resolve, so only the environment
variable overrides the default.

**Send bundles privately.** They contain the corpus text; the repo is public
and ships manifests, not documents. `data/bundles/` is gitignored. A bundle goes
stale when its builder re-fetches or changes chunking: re-export and re-send.

---

## Sources

| Source | Covers | Notes |
| --- | --- | --- |
| [ICRC IHL Databases](https://ihl-databases.icrc.org/) | Treaties, customary IHL | JSON:API, article-addressable — see below |
| [ICC](https://www.icc-cpi.int/) | ICC judgments | PDFs; paragraph numbers in the text |
| [ICTY](https://www.icty.org/) | ICTY judgments | PDFs; large |
| [ICJ](https://www.icj-cij.org/) | ICJ cases and advisory opinions | PDFs; huge — curation matters most here |
| [UN Digital Library](https://digitallibrary.un.org/) | Resolutions | Multiple formats |

Be polite: rate-limit, cache aggressively, identify the client in a User-Agent.
These are public institutional archives.

### How treaty text is actually fetched

The ICRC website is a single-page app: every URL returns the same ~2.6 KB HTML
shell with no treaty text in it. The text comes from the Drupal JSON:API behind
it, which is public and unauthenticated:

```
GET /jsonapi/node/treaty                              # 111 treaties, 50 per page
GET /jsonapi/node/treaty/{uuid}/field_treaty_content  # one treaty, by article
```

Each entry is one article, already separated — `field_treaty_content_unid` is
`article-51`, and the body is HTML with one `<p>` per numbered paragraph. The
whole treaty corpus is about nine requests.

Two things to know before relying on it:

- **It is undocumented.** There is no published contract, no versioning, no
  deprecation notice. Raw responses are snapshotted into `data/cache/` so a
  breaking change surfaces as a diff rather than silently emptying retrieval.
- **Sub-paragraphs are not separate elements.** `51(2)` is its own `<p>`, but
  `(a)`, `(b)`, `(c)` under it share one, newline-separated, and trailing
  clauses carry no marker at all. Getting to `8(2)(b)(iv)` means parsing the
  leading label with a depth stack — see the chunking section above.

`robots.txt` is `Disallow:` (empty — nothing excluded). The ICRC terms require
that material be copied entirely and unmodified with attribution, which is what
citation grounding needs anyway: spans store verbatim text and a `source_url`.

---

## Two instruments need explaining

Both decided in [ADR 0010](adr/0010-corpus-identity-and-amendments.md), because
corpus ids and locators are permanent once a run artifact is written.

### Hague IV is two corpus ids

| id | Document | Articles |
| --- | --- | --- |
| `hague_iv` | The 1907 Convention | 9 |
| `hague_iv_regs` | The annexed Regulations | 56 |

The Regulations renumber from 1, so both documents have an Article 1 and an
Article 3 saying entirely different things. **"Hague IV art. 23(g)" means the
Regulations** — that is where the law of means and methods lives, and the
Convention has no article 23.

The general rule: *a document that restarts article numbering is a separate
corpus id.*

### The Rome Statute is a consolidated text we assemble

One id, `rome_statute`, holding the statute **as amended**. The ICRC publishes
the base statute and seven amendments as separate documents, and the base is
itself already partly amended — it carries the 2019 starvation clause but stops
at `8(2)(e)(xii)`.

| Amendment | Treatment |
| --- | --- |
| War crimes 2010 (restates article 8, adds `8(2)(e)(xiii)`–`(xv)`) | Replaces the base article |
| Aggression 2010 (`8bis`, `15bis`, `15ter`) | Added as new articles |
| Article 124 deletion, 2015 | The article is not indexed |
| Three weapons amendments | **Not indexed** — see below |

ADR 0010 specifies that each span record which document its text came from, so
a result could state which version of article 8 the system argued from. That is
**not built yet**: spans carry only `locator`, `text`, `article` and `heading`.

**Known gap.** Three amendments insert a sentence into article 8 without the
source saying which sub-paragraph it becomes. They are not indexed, because a
guessed locator is worse than a missing one — it is indistinguishable from a
fabrication when a model cites the real provision. A citation to one of them
resolves `unresolved`, which the metrics read as fabrication. Say so in the
report.

---

## Current status

Both pipeline stages are built and tested: the fetcher downloads what the
manifests list, and the indexer writes the citation index and the Qdrant
collection. The index itself is a per-machine artifact (ADR 0007), shared
between machines as a bundle (ADR 0014). See [ISSUES.md](../ISSUES.md).
