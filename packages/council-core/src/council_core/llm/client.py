"""Thin async wrapper over LiteLLM.

LiteLLM already normalises four providers behind one call signature. This adds
the three things the debate needs on top: structured-output parsing with a
retry when a model returns prose instead of JSON, token accounting for the run
artifact, and logging that names the role rather than the raw model id.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

import structlog
from litellm import acompletion
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from council_core.llm.config import ModelConfig

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


class StructuredOutputError(RuntimeError):
    """A model's response could not be parsed into the expected schema."""


class ModelResponse(BaseModel):
    """One completion, plus what it cost.

    Token counts flow into `RunMetadata` so a run's cost is auditable after the
    fact — relevant here because three of the four roles run on free tiers with
    real quotas.
    """

    content: str
    model_id: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_seconds: float


class CouncilLLM:
    """Async model client shared by every role."""

    def __init__(self, config: ModelConfig, *, role: str = "unknown") -> None:
        self._config = config
        self._role = role

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def complete(
        self,
        *,
        system: str,
        user: str,
        seed: int | None = None,
    ) -> ModelResponse:
        """Send one completion request.

        Transport failures are retried with backoff; a model that answers badly
        is not retried here — that is the caller's business.
        """
        started = time.perf_counter()

        kwargs: dict[str, Any] = {
            "model": self._config.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "timeout": self._config.timeout_seconds,
        }
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base
        if self._config.extra_headers:
            kwargs["extra_headers"] = self._config.extra_headers
        if seed is not None:
            kwargs["seed"] = seed

        log.info("llm_request", role=self._role, model=self._config.model_id)
        response = await acompletion(**kwargs)
        elapsed = time.perf_counter() - started

        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)

        log.info(
            "llm_response",
            role=self._role,
            model=self._config.model_id,
            latency=round(elapsed, 2),
            chars=len(content),
        )

        return ModelResponse(
            content=content,
            model_id=self._config.model_id,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            latency_seconds=elapsed,
        )

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        seed: int | None = None,
        max_repairs: int = 1,
    ) -> tuple[T, ModelResponse]:
        """Complete and parse into `schema`.

        Small local models routinely wrap JSON in prose or fences. Rather than
        failing the turn, one repair attempt re-prompts with the validation
        error attached — cheaper and more reliable than tightening the prompt.
        """
        response = await self.complete(system=system, user=user, seed=seed)

        for attempt in range(max_repairs + 1):
            try:
                return schema.model_validate(_extract_json(response.content)), response
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                if attempt == max_repairs:
                    log.error(
                        "structured_output_failed",
                        role=self._role,
                        model=self._config.model_id,
                        error=str(exc)[:500],
                    )
                    raise StructuredOutputError(
                        f"{self._role} ({self._config.model_id}) did not return valid "
                        f"{schema.__name__}: {exc}"
                    ) from exc

                log.warning("structured_output_repair", role=self._role, attempt=attempt + 1)
                response = await self.complete(
                    system=system,
                    user=(
                        f"{user}\n\n---\n"
                        f"Your previous response could not be parsed: {exc}\n"
                        f"Return ONLY valid JSON matching the schema. No prose, no code fences."
                    ),
                    seed=seed,
                )

        raise StructuredOutputError("unreachable")


def _extract_json(content: str) -> Any:
    """Pull a JSON value out of a model response.

    Handles the three shapes models actually emit: bare JSON, a fenced block,
    and JSON with surrounding commentary.
    """
    text = content.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if fenced := _JSON_BLOCK.search(text):
        return json.loads(fenced.group(1))

    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    ends = [i for i in (text.rfind("}"), text.rfind("]")) if i != -1]
    if starts and ends:
        return json.loads(text[min(starts) : max(ends) + 1])

    raise ValueError("No JSON object found in the model response.")
