"""Embed corpus spans with fastembed.

The model must be the same one the API queries with. A collection built with
one model and searched with another returns plausible-looking nonsense and
raises nothing -- non-negotiable #3 -- so the name comes from `EMBEDDING_MODEL`
in both places and is written into the collection for good measure.
"""

from __future__ import annotations

from collections.abc import Iterator

import structlog
from fastembed import TextEmbedding

from council_core.models.corpus import Span

log = structlog.get_logger(__name__)


class Embedder:
    """Turns span text into vectors."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: TextEmbedding | None = None

    @property
    def model(self) -> TextEmbedding:
        """Lazy-load. The first call downloads the ONNX weights."""
        if self._model is None:
            log.info("loading_embedder", model=self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    @property
    def dimensions(self) -> int:
        """The vector width, read from the model rather than hardcoded."""
        for model in TextEmbedding.list_supported_models():
            if model["model"] == self.model_name:
                return int(model["dim"])
        raise ValueError(
            f"{self.model_name!r} is not a fastembed model. "
            f"Run TextEmbedding.list_supported_models() to see what is available."
        )

    def embed_spans(self, spans: list[Span], *, batch_size: int = 16) -> Iterator[list[float]]:
        """Embed each span in order.

        A span is embedded with its parent's locator prepended when it has one:
        some treaty articles are a single line, and "those which are not
        directed at a specific military objective" retrieves poorly without
        the article it qualifies.

        Spans are fed through in slices rather than handed over whole, so peak
        memory does not scale with the size of the document. The Rome Statute
        is 946 spans; embedding them in one call alongside a 1.2GB model is
        enough to get the process OOM-killed on a 16GB laptop.
        """
        for start in range(0, len(spans), batch_size):
            window = spans[start : start + batch_size]
            texts = [self._embedding_text(span) for span in window]
            for vector in self.model.embed(texts, batch_size=batch_size):
                yield vector.tolist()

    @staticmethod
    def _embedding_text(span: Span) -> str:
        """What actually gets embedded, which is not quite what gets stored.

        The payload keeps the provision verbatim -- a quotation is checked
        against it -- while the embedding may carry extra context.
        """
        if span.heading:
            return f"{span.heading}\n\n{span.text}"
        if span.parent:
            return f"{span.parent}\n\n{span.text}"
        return span.text
