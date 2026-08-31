"""Service configuration, loaded from environment.

One settings singleton, imported everywhere. Paths are container paths; the
compose files bind the host directories onto them.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from council_core.llm.config import RoleModels


class Settings(BaseSettings):
    """Runtime settings for the orchestrator API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", description="'development' or 'production'.")
    log_level: str = "INFO"
    log_json: bool = Field(default=False, description="True in production.")

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "ihl_corpus"
    embedding_model: str = Field(
        default="BAAI/bge-m3",
        description="fastembed model name. Must match what the indexer used.",
    )

    prompts_dir: Path = Path("/app/prompts")
    corpus_dir: Path = Path("/corpus")
    data_dir: Path = Path("/data")

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    max_concurrent_debates: int = Field(
        default=2,
        ge=1,
        description="Debates run four models each; unbounded concurrency exhausts free-tier quota.",
    )

    @property
    def runs_dir(self) -> Path:
        """Where run artifacts are persisted."""
        return self.data_dir / "runs"

    @property
    def citation_index_path(self) -> Path:
        """The locator -> span index the citation resolver reads."""
        return self.data_dir / "index" / "citation_index.json"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


@lru_cache
def get_role_models() -> RoleModels:
    """Cached model roster singleton."""
    return RoleModels()
