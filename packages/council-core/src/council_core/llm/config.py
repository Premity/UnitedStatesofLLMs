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

    model_id: str = Field(description="LiteLLM model id, e.g. 'groq/llama-3.3-70b-versatile'.")
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
        env_ignore_empty=True,  # .env.example ships `COUNCIL_SEED=` blank
        extra="ignore",
    )

    presenter_model: str = "groq/openai/gpt-oss-120b"
    presenter_temperature: float = 0.4

    attacker_doctrinal_model: str = "groq/qwen/qwen3.8-27b"
    attacker_doctrinal_temperature: float = 0.7

    attacker_evidentiary_model: str = "groq/openai/gpt-oss-20b"
    attacker_evidentiary_temperature: float = 0.7

    judge_model: str = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
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

        Hybrid-reasoning models -- Qwen3.5 under Ollama, Gemma 4 under the
        Gemini API, and nemotron-3-ultra under OpenRouter -- spend tokens on
        thinking before the answer, and the default 4096-token budget can be
        entirely consumed by that thinking with nothing left for the
        structured JSON response. Confirmed empirically against qwen3.5:9b
        (~6,300 completion tokens for one attacker turn), gemma-4-26b-a4b-it
        (hit the 4096 ceiling with *all 4093 tokens spent on reasoning*,
        returned empty content), and nemotron-3-ultra as judge in round 3 of a
        real debate (the dissent log grows every round, so the judge's
        response is the one place the correlation isn't just model-driven --
        round 3's ruling returned empty content on the first attempt and a
        JSON response truncated right near the end on the repair attempt,
        both the 4096-ceiling signature). All three families get the same
        much larger `max_tokens` and `timeout_seconds` as a result.
        """
        model_id: str = getattr(self, f"{role}_model")
        temperature: float = getattr(self, f"{role}_temperature")
        is_ollama = model_id.startswith("ollama/")
        is_hybrid_reasoning = (
            is_ollama
            or model_id.startswith("gemini/gemma")
            or model_id.startswith("openrouter/nvidia/nemotron")
        )

        return ModelConfig(
            model_id=model_id,
            temperature=temperature,
            api_base=self.ollama_base_url if is_ollama else None,
            max_tokens=16000 if is_hybrid_reasoning else 4096,
            timeout_seconds=600 if is_hybrid_reasoning else 180,
        )
