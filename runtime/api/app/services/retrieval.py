"""Corpus retrieval over Qdrant.

Embeds the query with BGE-M3 via fastembed (ONNX — no torch anywhere in this
repo, see `docs/adr/0001-no-torch-fastembed.md`) and returns corpus spans as
`ResolvedCitation`s, so retrieved context and model-emitted citations share one
type all the way through to the frontend.

`encode` runs in a thread executor: fastembed is synchronous and would otherwise
block the event loop while four model calls are in flight.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache

import structlog
from fastembed import TextEmbedding
from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)

log = structlog.get_logger(__name__)


class RetrievalService:
    """Semantic search over the indexed IHL corpus."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncQdrantClient(url=settings.qdrant_url)
        self._collection = settings.qdrant_collection
        self._model_name = settings.embedding_model
        self._embedder: TextEmbedding | None = None

    def _get_embedder(self) -> TextEmbedding:
        """Lazy-load the embedding model. First call downloads the ONNX weights."""
        if self._embedder is None:
            log.info("loading_embedder", model=self._model_name)
            self._embedder = TextEmbedding(model_name=self._model_name)
        return self._embedder

    async def embed(self, text: str) -> list[float]:
        """Embed one string, off the event loop."""

        def _encode() -> list[float]:
            return next(iter(self._get_embedder().embed([text]))).tolist()

        return await asyncio.to_thread(_encode)

    async def search(self, query: str, *, top_k: int = 8) -> list[ResolvedCitation]:
        """Retrieve the most relevant corpus spans for a query."""
        vector = await self.embed(query)

        results = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        )

        spans: list[ResolvedCitation] = []
        for point in results.points:
            payload = point.payload or {}
            spans.append(
                ResolvedCitation(
                    citation=Citation(
                        type=CitationType(payload.get("citation_type", "treaty")),
                        instrument=payload.get("instrument", "unknown"),
                        article=payload.get("article"),
                        case_id=payload.get("case_id"),
                        paragraph=payload.get("paragraph"),
                        rule_number=payload.get("rule_number"),
                    ),
                    status=CitationStatus.RESOLVED,
                    corpus_text=payload.get("text", ""),
                    source_url=payload.get("source_url"),
                )
            )

        log.info("retrieval_search", query_chars=len(query), returned=len(spans))
        return spans

    async def health(self) -> bool:
        """Whether Qdrant is reachable and the collection exists."""
        try:
            await self._client.get_collection(self._collection)
        except Exception as exc:
            log.warning("qdrant_unhealthy", error=str(exc))
            return False
        return True


class StubRetrievalService:
    """Serves context from the hand-written citation index, ranked by word overlap.

    Stands in for Qdrant until the indexer exists (T0-2), so roles have real
    authority to cite. Not semantic search, and never used unless
    `RETRIEVAL_BACKEND=stub` is set explicitly.
    """

    def __init__(self) -> None:
        self._path = get_settings().citation_index_path

    def _entries(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            raise FileNotFoundError(f"Stub retrieval needs a citation index at {self._path}.")
        return json.loads(self._path.read_text(encoding="utf-8")).get("entries", {})

    async def search(self, query: str, *, top_k: int = 8) -> list[ResolvedCitation]:
        """Return the index entries sharing the most words with the query."""
        query_tokens = set(query.lower().split())
        ranked = sorted(
            self._entries().items(),
            key=lambda item: len(query_tokens & set(item[1]["text"].lower().split())),
            reverse=True,
        )
        spans = [
            ResolvedCitation(
                citation=_citation_from_locator(locator),
                status=CitationStatus.RESOLVED,
                corpus_text=entry["text"],
                source_url=entry.get("source_url"),
            )
            for locator, entry in ranked[:top_k]
        ]
        log.warning("retrieval_stub_used", returned=len(spans), index=str(self._path))
        return spans

    async def health(self) -> bool:
        """Whether the stub index file exists."""
        return self._path.exists()


def _citation_from_locator(locator: str) -> Citation:
    """Invert `Citation.locator()` for the treaty and case forms the stub index holds."""
    head, _, tail = locator.partition("/")
    if tail.startswith("art."):
        return Citation(type=CitationType.TREATY, instrument=head, article=tail[4:])
    if tail.startswith("para."):
        return Citation(type=CitationType.CASE, instrument=head, case_id=head, paragraph=tail[5:])
    raise ValueError(f"Stub index locator not understood: {locator}")


@lru_cache
def get_retrieval_service() -> RetrievalService | StubRetrievalService:
    """Cached service singleton. The backend is chosen by `RETRIEVAL_BACKEND`."""
    if get_settings().retrieval_backend == "stub":
        return StubRetrievalService()
    return RetrievalService()
