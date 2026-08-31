"""Resolves model-emitted citations against the indexed corpus.

The contract is simple and strict: a citation is believed only if its locator
exists in the corpus index. Everything else is flagged. A model cannot talk its
way past this, because the check never reads the model's prose — only its
structured locator.

Three outcomes are deliberately distinguished:

  RESOLVED       the locator exists; the corpus text is attached
  OUT_OF_CORPUS  the instrument is real but not indexed (Tier 3) — unverifiable,
                 not necessarily fabricated
  UNRESOLVED     the locator does not exist where it should — the fabrication signal

Conflating the last two would make the citation-validity metric meaningless, so
they stay separate all the way through to the evaluation report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import structlog

from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)

log = structlog.get_logger(__name__)


class CorpusIndex(Protocol):
    """Lookup surface the resolver needs from whatever holds the corpus.

    Kept as a Protocol so the resolver can be unit-tested against an in-memory
    dict without standing up Qdrant.
    """

    def lookup(self, locator: str) -> tuple[str, str | None] | None:
        """Return `(corpus_text, source_url)` for a locator, or None if absent."""
        ...

    def knows_instrument(self, instrument: str) -> bool:
        """Whether this instrument is indexed at all.

        Distinguishes 'we indexed this treaty but not that article' (a real
        miss, likely fabrication) from 'we never indexed this instrument'
        (out of corpus, unverifiable).
        """
        ...


class JsonCorpusIndex:
    """A `CorpusIndex` backed by the flat JSON index the indexer emits.

    Built by `pipeline/indexer` at `data/index/citation_index.json`, mapping
    locator string -> {text, source_url}. Small enough to hold in memory: the
    curated corpus is tens of thousands of spans, not millions.
    """

    def __init__(self, index_path: Path) -> None:
        self._path = index_path
        self._entries: dict[str, dict[str, str]] = {}
        self._instruments: set[str] = set()
        self._loaded = False

    def load(self) -> None:
        """Read the index from disk. Idempotent."""
        if self._loaded:
            return
        if not self._path.exists():
            log.warning("citation_index_missing", path=str(self._path))
            self._loaded = True
            return

        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._entries = raw.get("entries", {})
        self._instruments = set(raw.get("instruments", []))
        self._loaded = True
        log.info(
            "citation_index_loaded",
            entries=len(self._entries),
            instruments=len(self._instruments),
        )

    def lookup(self, locator: str) -> tuple[str, str | None] | None:
        self.load()
        entry = self._entries.get(locator)
        if entry is None:
            return None
        return entry["text"], entry.get("source_url")

    def knows_instrument(self, instrument: str) -> bool:
        self.load()
        return instrument in self._instruments


class CitationResolver:
    """Validates citations against a corpus index.

    Stateless apart from the index, so it is safe to share across requests.
    """

    def __init__(self, index: CorpusIndex, *, quote_match_threshold: float = 0.6) -> None:
        self._index = index
        self._quote_threshold = quote_match_threshold

    def resolve(self, citation: Citation) -> ResolvedCitation:
        """Resolve one citation to a verdict."""
        if (incomplete := self._locator_gap(citation)) is not None:
            return ResolvedCitation(
                citation=citation,
                status=CitationStatus.UNRESOLVED,
                note=incomplete,
            )

        locator = citation.locator()
        hit = self._index.lookup(locator)

        if hit is None:
            known = self._index.knows_instrument(citation.instrument)
            return ResolvedCitation(
                citation=citation,
                status=CitationStatus.UNRESOLVED if known else CitationStatus.OUT_OF_CORPUS,
                note=(
                    f"No span at {locator} in an indexed instrument."
                    if known
                    else f"Instrument '{citation.instrument}' is not in the indexed corpus."
                ),
            )

        corpus_text, source_url = hit

        if citation.quoted_text and not self._quote_matches(citation.quoted_text, corpus_text):
            return ResolvedCitation(
                citation=citation,
                status=CitationStatus.MISQUOTED,
                corpus_text=corpus_text,
                source_url=source_url,
                note="Quoted text does not appear at this locator.",
            )

        return ResolvedCitation(
            citation=citation,
            status=CitationStatus.RESOLVED,
            corpus_text=corpus_text,
            source_url=source_url,
        )

    def resolve_all(self, citations: list[Citation]) -> list[ResolvedCitation]:
        """Resolve a batch, preserving order."""
        return [self.resolve(c) for c in citations]

    @staticmethod
    def _locator_gap(citation: Citation) -> str | None:
        """Return a reason string if the citation lacks fields its type requires."""
        match citation.type:
            case CitationType.TREATY if not citation.article:
                return "Treaty citation is missing an article locator."
            case CitationType.CASE if not (citation.case_id and citation.paragraph):
                return "Case citation requires both a case id and a paragraph."
            case CitationType.CUSTOMARY if citation.rule_number is None:
                return "Customary IHL citation is missing a rule number."
            case _:
                return None

    def _quote_matches(self, quoted: str, corpus_text: str) -> bool:
        """Loose containment check for a claimed quotation.

        Deliberately lenient: models normalise whitespace, elide with ellipses,
        and drop internal citations. The goal is to catch text that is *not
        there at all*, not to police punctuation. Token overlap above the
        threshold counts as a match.
        """
        quoted_tokens = set(quoted.lower().split())
        if not quoted_tokens:
            return True
        corpus_tokens = set(corpus_text.lower().split())
        overlap = len(quoted_tokens & corpus_tokens) / len(quoted_tokens)
        return overlap >= self._quote_threshold
