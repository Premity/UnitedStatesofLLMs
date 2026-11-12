"""Thin async wrapper over LiteLLM.

LiteLLM already normalises four providers behind one call signature. This adds
the three things the debate needs on top: structured-output parsing with a
retry when a model returns prose instead of JSON, token accounting for the run
artifact, and logging that names the role rather than the raw model id.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, TypeVar

import litellm
import structlog
from litellm import acompletion
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from council_core.llm.config import ModelConfig

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)

# 429 is rate limiting; the rest are transient server-side failures that go
# away on their own. Deliberately excludes 400/401/403/404 and the like --
# those are permanent, and retrying them just delays the failure by a minute.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    """True for transport failures and transient server errors from any provider.

    Started as a fixed tuple of LiteLLM exception types (RateLimitError,
    APIConnectionError, Timeout, InternalServerError) after a live run hit
    Groq's per-minute token limit and wasn't retried at all. That tuple then
    missed `ServiceUnavailableError` (Gemini's 503 "high demand", the same
    error that made `gemini-3.8-flash` unusable for over a week) and a whole
    debate failed outright on the first hit -- no retry attempt at all.

    Every LiteLLM exception sets `status_code` unconditionally in `__init__`
    (confirmed against the installed version's source for RateLimitError,
    APIConnectionError, Timeout, InternalServerError, and
    ServiceUnavailableError), so matching on the code generalizes across
    provider-specific subclasses instead of enumerating them one at a time --
    this predicate has already needed extending twice.
    """
    # litellm.Timeout sets status_code=408, which isn't a server error and
    # deliberately isn't in the retryable set above -- a request timeout is
    # always worth retrying regardless of code, so it's checked by type.
    if isinstance(exc, (TimeoutError, ConnectionError, litellm.exceptions.Timeout)):
        return True
    return getattr(exc, "status_code", None) in _RETRYABLE_STATUS_CODES


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

    async def complete(
        self,
        *,
        system: str,
        user: str,
        seed: int | None = None,
    ) -> ModelResponse:
        """Send one completion request, bounded by a total wall-clock deadline.

        `_complete_with_retry` retries individual transport failures with
        backoff, but `stop_after_attempt(6)` alone caps *attempts*, not time --
        six attempts at `timeout_seconds` each (plus backoff) is unbounded
        with respect to the role's actual time budget: for a hybrid-reasoning
        role at 600s/attempt that is ~62 minutes for one `complete()` call, and
        `complete_structured` can call it twice (initial + one repair) -- close
        to two hours holding a debate slot for a single stuck model (GitHub
        #11-2). `total_timeout_seconds` is a second, independent ceiling on
        the whole retry loop, so a stuck model fails the turn in minutes
        instead of hours regardless of how the per-attempt numbers above
        change.
        """
        try:
            async with asyncio.timeout(self._config.total_timeout_seconds):
                return await self._complete_with_retry(system=system, user=user, seed=seed)
        except TimeoutError:
            log.error(
                "llm_total_timeout",
                role=self._role,
                model=self._config.model_id,
                total_timeout_seconds=self._config.total_timeout_seconds,
            )
            raise

    @retry(
        stop=stop_after_attempt(6),
        # 6 attempts at this backoff spans 62s cumulative before the last one
        # (2+4+8+16+32, verified against the installed tenacity) -- needed
        # to actually cross Groq's per-minute rate-limit window, confirmed
        # against a live run that hit it. multiplier=1 only reaches 32s here
        # (GitHub #10) and would exhaust the whole retry budget still inside
        # the rate-limit window.
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    async def _complete_with_retry(
        self,
        *,
        system: str,
        user: str,
        seed: int | None = None,
    ) -> ModelResponse:
        """One completion request, retried on transport failure.

        A model that answers badly is not retried here — that is the caller's
        business. Called only through `complete()`, which adds the total
        wall-clock deadline this retry loop has no concept of on its own.
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
