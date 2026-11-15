# 0014 — One machine embeds the corpus; the others import its index

**Status:** Accepted
**Date:** 2026-11-15

## Context

ADR 0007 made the corpus a per-machine artifact: the manifests travel, and each
machine fetches and indexes for itself. Two things went wrong with that.

- **Not every machine can index.** Fetching is a few megabytes of downloads.
  Embedding is not: the indexer loads a 1.2GB model and embeds every span, and
  on a 16GB laptop it took the editor down twice. That machine kept a partial
  index, so its citation statuses meant little and its retrieval found less.
- **Results from two machines could not be compared.** Since GitHub #24 every
  result records the citation index that scored it, and the report refuses to
  pool different ones. Two machines that each build their own index will
  differ whenever their fetches did.

## Decision

**The machine that can embed builds the index and exports it; the others
import it.** `make export-index` writes one tar file holding the Qdrant
collection snapshot, the citation index, and a manifest of the settings it was
built with. `make import-index FILE=…` loads both halves.
`make index-status` prints a one-line fingerprint (corpus hash, embedding
model, point count, Qdrant version); two machines hold the same index when
their fingerprints match.

**The two halves travel together.** The citation index decides what counts as
fabrication and the collection decides what retrieval can find. A pair from
two different builds is wrong with no error, so they are one file.

**Every silent failure is checked, because none of them raises on its own.**

| Check | Where | What it catches |
| --- | --- | --- |
| Points = locators | export, status | An embedding run killed partway, or a collection from another build |
| Vector width = the model's width | export, status | A collection built with another embedding model |
| `EMBEDDING_MODEL` matches the bundle's | import, status | Queries embedded by a different model than the corpus was (non-negotiable #3) |
| Qdrant version matches | import | A snapshot from a server off the compose pin |
| Citation index hash = manifest's | import | A file altered or truncated in transit |
| Point count and width after restore | import | A restore that came out wrong; the citation index is not written |

Qdrant is restored before the citation index is written. If the upload
itself fails, nothing on this machine has changed. If it succeeds but the
post-restore check fails, the collection has already been replaced while the
citation index has not, so the two no longer match: the import says so, and
`index-status` flags it (points ≠ locators) until a good bundle is imported or
the indexer is re-run.

**Bundles travel privately, never in the repo.** They hold the corpus text.
The repo is public, ships manifests rather than data (ADR 0007), and nobody has
checked the redistribution terms of the treaty texts or of the Rome Statute
consolidation (ADR 0010). `data/bundles/` is gitignored.

## Consequences

**Gained:** a machine that cannot embed gets the full index. Every machine on
the same bundle scores citations identically, so their results carry the same
corpus hash and the report pools them.

**Given up:**

- One machine is now the source of the index, and a bundle goes stale when it
  re-fetches or changes chunking. `index-status` flags a citation index that
  changed after an import, but a new bundle has to be sent by hand.
- A bundle is tied to a Qdrant version and an embedding model. Changing either
  means rebuilding and re-sending.

**What this does not change:** ADR 0007's scope. Manifests still define the
corpus and the fetcher still never crawls; a bundle is a built copy of the
same scope, not a different one.

**What would make us revisit this:** a shared Qdrant everyone points at, or an
index small enough that every machine can embed it.
