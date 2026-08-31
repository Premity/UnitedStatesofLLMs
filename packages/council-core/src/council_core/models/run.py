"""The persisted record of a single debate.

A run artifact must be sufficient to *reproduce and audit* the debate: which
models answered, under what settings, against which prompt versions, over which
retrieved spans. Without this the dissent log has no provenance and the
evaluation is not reproducible.

Artifacts are written as JSON to `data/runs/<run_id>/artifact.json`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from council_core.models.debate import DebateState


class RunStatus(StrEnum):
    """Lifecycle of a run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunMetadata(BaseModel):
    """Everything needed to reproduce a run, recorded at execution time.

    Model *ids* are resolved rather than templated: if config says
    `ollama/qwen3.5` and Ollama serves `qwen3.5:14b-q4`, the resolved string is
    what gets recorded, because that is what actually answered.
    """

    run_id: str
    status: RunStatus = RunStatus.PENDING

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    role_models: dict[str, str] = Field(
        default_factory=dict,
        description="Role name -> resolved model id, as actually invoked.",
    )
    temperatures: dict[str, float] = Field(default_factory=dict)
    seed: int | None = Field(default=None, description="Set where the backend honours it.")

    prompt_hashes: dict[str, str] = Field(
        default_factory=dict,
        description="Prompt id -> SHA-256 of the template. Detects silent prompt drift.",
    )
    corpus_version: str | None = Field(
        default=None,
        description="Corpus manifest version the retrieval index was built from.",
    )
    council_version: str = Field(default="0.1.0")

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    duration_seconds: float | None = None

    error: str | None = None


class RunArtifact(BaseModel):
    """A complete, self-contained record of one debate.

    This is the file the evaluation harness reads in bulk and the export
    renderers turn into a reviewable document.
    """

    metadata: RunMetadata
    state: DebateState

    def to_json(self) -> str:
        """Serialise for `data/runs/<run_id>/artifact.json`."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, raw: str) -> RunArtifact:
        """Load a persisted artifact."""
        return cls.model_validate_json(raw)
