# Corpus manifests

The manifests are the **scope of the corpus**. The fetcher downloads what they
list and nothing else — it never crawls. Adding a source means editing a
manifest, which makes every change to the corpus a reviewable diff.

| File | Tier | What it holds |
| --- | --- | --- |
| `treaties.json` | 1 | Treaty text, committed to the repo under `corpus/treaties/` |
| `cases.json` | 2 | Curated jurisprudence, fetched into gitignored `data/cache/` |
| `resolutions.json` | 1 | UN resolutions, committed |

## Why curated rather than complete

Ingesting every ICJ and ICTY judgment would take weeks, produce tens of
gigabytes, and make retrieval *worse* — a proportionality question does not
benefit from having maritime delimitation cases in the index. The corpus is
scoped to what the evaluation cases and the demo actually need.

Authority outside the corpus is not silently accepted. A citation to an
unindexed instrument resolves as `out_of_corpus` — unverifiable, and reported
separately from `unresolved`, which is the fabrication signal. See
`docs/adr/0004-citation-integrity.md`.

## Adding a case

1. Add an entry to `cases.json` with `id`, `court`, `year`, `url`, and the
   `paragraphs` range that matters.
2. Run `make fetch` to download it, then `make index` to embed it.
3. The `id` becomes the citation locator, so it must be stable — models cite
   `icty_galic_tj/para.58`, and renaming the id breaks every stored run that
   referenced it.
