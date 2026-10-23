"""Corpus indexer entrypoint.

Reads the documents the fetcher wrote, embeds them, upserts into Qdrant, and
writes the citation index the runtime validator reads.

    make index      # Qdrant must be up

Chunking granularity is not a tuning knob -- it is a correctness requirement,
and it has already happened by the time this runs. The fetcher splits treaties
at article and sub-paragraph, because those numbers *are* the citation
locators. This stage only embeds what it is given.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog
from qdrant_client import QdrantClient

from council_core.models.corpus import CorpusDocument
from council_core.telemetry import configure_logging
from indexer.embeddings.embedder import Embedder
from indexer.index.citation_index import write_index
from indexer.index.qdrant_store import ensure_collection, upsert_document

log = structlog.get_logger(__name__)

CORPUS_DIR = Path(os.getenv("CORPUS_DIR", "/corpus"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = DATA_DIR / "cache"
INDEX_PATH = DATA_DIR / "index" / "citation_index.json"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "ihl_corpus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")


def load_documents(cache_dir: Path) -> list[CorpusDocument]:
    """Read what the fetcher wrote. `raw/` holds API snapshots, not documents."""
    documents = []
    for path in sorted(cache_dir.glob("*.json")):
        documents.append(CorpusDocument.model_validate_json(path.read_text(encoding="utf-8")))
    return documents


def main() -> None:
    """Chunk, embed, and index the corpus."""
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    documents = load_documents(CACHE_DIR)
    if not documents:
        raise SystemExit(f"No documents in {CACHE_DIR}. Run `make fetch` first.")

    total_spans = sum(len(d.spans) for d in documents)
    log.info(
        "index_start",
        qdrant=QDRANT_URL,
        collection=COLLECTION,
        model=EMBEDDING_MODEL,
        documents=len(documents),
        spans=total_spans,
    )

    # The citation index first: it needs no network, and it is what makes
    # citation validation work at all. If Qdrant is unreachable the run still
    # leaves the resolver with a usable index.
    write_index(documents, INDEX_PATH)

    embedder = Embedder(EMBEDDING_MODEL)
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, COLLECTION, dimensions=embedder.dimensions)

    written = 0
    for document in documents:
        vectors = embedder.embed_spans(document.spans)
        written += upsert_document(client, COLLECTION, document, vectors)

    log.info("index_complete", points=written, collection=COLLECTION)


if __name__ == "__main__":
    main()
