"""Tests for `RoleModels.for_role()`'s hybrid-reasoning token budget.

The budget allowlist has already grown three times for three different
providers (Ollama, Gemini, OpenRouter) and missed a fourth (Groq's reasoning
models, GitHub #9) — the exact "model too small" failure signature each time.
A table test over every shipped default, keyed by model id rather than env
vars, catches the next roster change too.
"""

from __future__ import annotations

import pytest

from council_core.llm.config import RoleModels

# Model id -> whether it should get the elevated hybrid-reasoning budget.
# Constructed via an explicit kwarg (not .env) so the test is independent of
# whatever happens to be configured in the developer's environment.
_CASES: list[tuple[str, bool]] = [
    # Shipped defaults (packages/council-core/src/council_core/llm/config.py).
    ("groq/openai/gpt-oss-120b", False),  # presenter -- plain instruction-tuned
    ("groq/qwen/qwen3.8-27b", True),  # attacker_doctrinal -- reasoning model
    ("groq/openai/gpt-oss-20b", True),  # attacker_evidentiary -- reasoning model
    ("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", True),  # judge
    # Other hybrid-reasoning families this budget logic has already covered.
    ("ollama/qwen3.5:9b", True),
    ("gemini/gemma-4-31b-it", True),
    ("gemini/gemma-4-26b-a4b-it", True),
    # A Groq model that is not a reasoning model must not get the elevated
    # budget just because it shares the `groq/` prefix with ones that are.
    ("groq/llama-3.3-70b-versatile", False),
]


@pytest.mark.parametrize(("model_id", "is_hybrid_reasoning"), _CASES)
def test_for_role_budget_matches_each_model_family(
    model_id: str, is_hybrid_reasoning: bool
) -> None:
    roles = RoleModels(presenter_model=model_id)
    config = roles.for_role("presenter")

    expected_max_tokens = 16000 if is_hybrid_reasoning else 4096
    expected_timeout = 600 if is_hybrid_reasoning else 180
    assert config.max_tokens == expected_max_tokens
    assert config.timeout_seconds == expected_timeout
