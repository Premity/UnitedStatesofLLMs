"""Per-role model configuration.

Every role's backend is a config string, never a code path. Switching the
attackers from local Ollama to Cloudflare Workers AI for a hosted demo is an
env-var change, which is exactly what the project proposal requires.

Model id format is LiteLLM's: `<provider>/<model>`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseModel):
    """How one role talks to one model."""

    model_id: str = Field(description="LiteLLM model id, e.g. 'mistral/magistral-medium-latest'.")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout_seconds: int = Field(default=180, gt=0)

    api_base: str | None = Field(
        default=None,
        description="Override the provider endpoint. Used to point Ollama at a host or container.",
    )
    extra_headers: dict[str, str] = Field(default_factory=dict)


class RoleModels(BaseSettings):
    """The council's full model roster, loaded from environment.

    Defaults match the configuration in the project proposal: frontier models by
    API for the two roles that set quality (presenter, judge), local small models
    for the two attackers.
    """

    model_config = SettingsConfigDict(
        env_prefix="COUNCIL_",
        env_file=".env",
        extra="ignore",
    )

    presenter_model: str = "mistral/magistral-medium-latest"
    presenter_temperature: float = 0.4

    attacker_doctrinal_model: str = "ollama/qwen3.5:14b"
    attacker_doctrinal_temperature: float = 0.7

    attacker_evidentiary_model: str = "ollama/gemma3:12b"
    attacker_evidentiary_temperature: float = 0.7

    judge_model: str = "gemini/gemini-2.5-pro"
    judge_temperature: float = 0.2

    ollama_base_url: str = Field(
        default="http://host.docker.internal:11434",
        description=(
            "Where Ollama lives. Defaults to the host, so teammates share one model "
            "store. Set to http://ollama:11434 when running the optional compose profile."
        ),
    )

    seed: int | None = Field(
        default=None,
        description="Passed to backends that honour it. Does not guarantee determinism.",
    )

    def for_role(self, role: str) -> ModelConfig:
        """Build the `ModelConfig` for a role name.

        Ollama-backed roles get `api_base` injected so one setting moves every
        local model between host and container.
        """
        model_id: str = getattr(self, f"{role}_model")
        temperature: float = getattr(self, f"{role}_temperature")

        return ModelConfig(
            model_id=model_id,
            temperature=temperature,
            api_base=self.ollama_base_url if model_id.startswith("ollama/") else None,
        )
