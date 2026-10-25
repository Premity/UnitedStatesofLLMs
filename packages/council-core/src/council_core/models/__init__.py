"""Domain models for the debate, its citations, and its persisted artifacts."""

from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)
from council_core.models.corpus import (
    CorpusDocument,
    DocumentType,
    Span,
)
from council_core.models.debate import (
    Argument,
    DebateConfig,
    DebateState,
    Objection,
    ObjectionDisposition,
    Role,
    Turn,
    Verdict,
)
from council_core.models.run import RunArtifact, RunMetadata, RunStatus

__all__ = [
    "Argument",
    "Citation",
    "CitationStatus",
    "CitationType",
    "CorpusDocument",
    "DebateConfig",
    "DebateState",
    "DocumentType",
    "Objection",
    "ObjectionDisposition",
    "ResolvedCitation",
    "Role",
    "RunArtifact",
    "RunMetadata",
    "RunStatus",
    "Span",
    "Turn",
    "Verdict",
]
