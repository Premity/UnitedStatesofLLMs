"""Upsert embedded spans into Qdrant.

The payload here is read back by `RetrievalService` in the API, which rebuilds
a `Citation` from it. The field names are therefore a contract between the two
-- see `docs/corpus.md` -- and `locator` is the join to the citation index.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from council_core.models.corpus import CorpusDocument, DocumentType, Span

log = structlog.get_logger(__name__)

# A locator is unique and permanent, so deriving the point id from it makes
# re-indexing idempotent: the same provision overwrites itself rather than
# accumulating duplicates that split retrieval between stale and fresh copies.
POINT_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def point_id(locator: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, locator))


def span_payload(document: CorpusDocument, span: Span) -> dict:
    """The payload the API expects. Field names are a contract."""
    is_case = document.type is DocumentType.CASE
    return {
        "locator": span.locator,
        "citation_type": document.type.value,
        "instrument": document.id,
        "article": span.article,
        "case_id": document.id if is_case else None,
        "paragraph": span.paragraph,
        "rule_number": None,
        "text": span.text,
        "source_url": document.source_url,
    }


def ensure_collection(client: QdrantClient, name: str, *, dimensions: int) -> None:
    """Create the collection, or check the existing one has the right width.

    A collection built at one vector width cannot be queried at another, and a
    model swap is the likeliest cause -- so fail loudly rather than let the
    upsert error point somewhere less useful.
    """
    if client.collection_exists(name):
        existing = client.get_collection(name).config.params.vectors.size
        if existing != dimensions:
            raise ValueError(
                f"Collection {name!r} holds {existing}-dimension vectors but the embedder "
                f"produces {dimensions}. The embedding model changed: drop the collection "
                f"and re-index (make reset-qdrant, then make corpus)."
            )
        return

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
    )
    log.info("collection_created", name=name, dimensions=dimensions)


def upsert_document(
    client: QdrantClient,
    collection: str,
    document: CorpusDocument,
    vectors: Iterable[list[float]],
    *,
    batch_size: int = 128,
) -> int:
    """Write one document's spans. Returns how many points were written."""
    points: list[PointStruct] = []
    written = 0

    for span, vector in zip(document.spans, vectors, strict=True):
        points.append(
            PointStruct(
                id=point_id(span.locator),
                vector=vector,
                payload=span_payload(document, span),
            )
        )
        if len(points) >= batch_size:
            client.upsert(collection_name=collection, points=points)
            written += len(points)
            points = []

    if points:
        client.upsert(collection_name=collection, points=points)
        written += len(points)

    log.info("document_upserted", id=document.id, points=written)
    return written
