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


@lru_cache
def get_retrieval_service() -> RetrievalService:
    """Cached service singleton."""
    return RetrievalService()
