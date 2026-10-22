"""Corpus indexer entrypoint.

Chunks the corpus at citation granularity, embeds it with BGE-M3 via fastembed,
upserts into Qdrant, and writes the citation resolution index the runtime
validator reads.

    make index      # runtime stack must be up — this writes into its Qdrant

STATUS: scaffold. Collection setup and the citation-index format are settled;
chunking and embedding are not yet implemented. See `docs/corpus.md`.

Chunking granularity is not a tuning knob — it is a correctness requirement.
Judgments chunk per numbered paragraph and treaties per article, because those
numbers *are* the citation locators. Chunking by token window would make
`icty_galic_tj/para.58` unresolvable.
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from council_core.telemetry import configure_logging

log = structlog.get_logger(__name__)

CORPUS_DIR = Path(os.getenv("CORPUS_DIR", "/corpus"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "ihl_corpus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")


def main() -> None:
    """Chunk, embed, and index the corpus."""
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    log.info(
        "index_start",
        qdrant=QDRANT_URL,
        collection=COLLECTION,
        model=EMBEDDING_MODEL,
    )

    # TODO(#3): implement indexing.
    #   1. Read committed treaties from corpus/ and fetched cases from data/cache/
    #   2. Chunk at citation granularity  -> app/chunking/
    #        treaties:  one chunk per article/subparagraph
    #        judgments: one chunk per numbered paragraph
    #   3. Embed with fastembed BGE-M3    -> app/embeddings/
    #   4. Upsert to Qdrant with payload  -> app/index/
    #        {citation_type, instrument, article, case_id, paragraph,
    #         rule_number, text, source_url}
    #   5. Write data/index/citation_index.json:
    #        {"instruments": [...], "entries": {"<locator>": {"text", "source_url"}}}
    #
    # Step 5 is what makes the citation validator work — without it every
    # citation resolves as out_of_corpus.
    log.warning("indexer_not_implemented", next_step="see docs/corpus.md and ISSUES.md")


if __name__ == "__main__":
    main()
