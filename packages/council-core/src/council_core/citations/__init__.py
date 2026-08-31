"""Citation extraction, resolution, and validation.

The anti-fabrication machinery. See `docs/adr/0004-citation-integrity.md`.
"""

from council_core.citations.resolver import CitationResolver, CorpusIndex

__all__ = ["CitationResolver", "CorpusIndex"]
