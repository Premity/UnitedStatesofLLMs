"""Domain models for the debate, its citations, and its persisted artifacts."""

from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)
from council_core.models.corpus import (
    CorpusDocument,
    CorpusIdentity,
    DocumentType,
    Span,
)
from council_core.models.debate import (
    Argument,
    DebateConfig,
    DebateState,
    Objection,
    ObjectionDisposition,
    ObjectionSeverity,
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
    "CorpusIdentity",
    "DebateConfig",
    "DebateState",
    "DocumentType",
    "Objection",
    "ObjectionDisposition",
    "ObjectionSeverity",
    "ResolvedCitation",
    "Role",
    "RunArtifact",
    "RunMetadata",
    "RunStatus",
    "Span",
    "Turn",
    "Verdict",
]
