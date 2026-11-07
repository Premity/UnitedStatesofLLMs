"""Tests for `CouncilLLM.complete()`'s total wall-clock deadline.

Without it, a model that fails every attempt holds the slot for
`timeout_seconds x 6 attempts` plus backoff -- about an hour for a
hybrid-reasoning role, doubled again by `complete_structured`'s one repair
(GitHub #11-2). `total_timeout_seconds` is a second ceiling around the whole
retry loop that is independent of attempt count.
"""

from __future__ import annotations

import asyncio

import pytest

from council_core.llm import client as client_module
from council_core.llm.client import CouncilLLM
from council_core.llm.config import ModelConfig


class _RetryableError(Exception):
    """Stands in for a LiteLLM exception that `_is_retryable` would retry."""

    def __init__(self) -> None:
        super().__init__("service unavailable")
        self.status_code = 503


async def test_total_timeout_cuts_off_a_stuck_model_well_before_all_retries_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def always_fails(**_: object) -> None:
        raise _RetryableError()

    monkeypatch.setattr(client_module, "acompletion", always_fails)

    config = ModelConfig(
        model_id="groq/does-not-matter",
        total_timeout_seconds=1,  # far below the ~62s full retry+backoff budget
    )
    llm = CouncilLLM(config, role="test")

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(10):  # guards the test itself against hanging
            await llm.complete(system="s", user="u")
