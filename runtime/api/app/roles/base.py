"""Shared plumbing for every role.

Handles the parts that are identical across roles: building the LLM client from
config, rendering prompts, timing the turn, and resolving every citation the
model emitted before the turn is recorded.

Citation resolution happens *here*, at the boundary, so no downstream code has
to remember to do it. An argument reaches the judge already marked grounded or
unsupported.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from app.core.config import get_role_models, get_settings
from council_core.citations import CitationResolver
from council_core.citations.resolver import JsonCorpusIndex
from council_core.llm import CouncilLLM, ModelResponse
from council_core.models.debate import Argument, Objection, Role, Turn
from council_core.prompts import PromptLoader, RenderedPrompt

log = structlog.get_logger(__name__)

_prompt_loader: PromptLoader | None = None
_resolver: CitationResolver | None = None


def get_prompt_loader() -> PromptLoader:
    """Shared prompt loader singleton."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader(get_settings().prompts_dir)
    return _prompt_loader


def get_resolver() -> CitationResolver:
    """Shared citation resolver singleton."""
    global _resolver
    if _resolver is None:
        _resolver = CitationResolver(JsonCorpusIndex(get_settings().citation_index_path))
    return _resolver


class BaseRole:
    """Common behaviour for the presenter, attackers, and judge."""

    role: Role

    def __init__(self, role: Role | None = None) -> None:
        if role is not None:
            self.role = role
        self._models = get_role_models()
        self._config = self._models.for_role(self.role.value)
        self._llm = CouncilLLM(self._config, role=self.role.value)
        self._prompts = get_prompt_loader()
        self._resolver = get_resolver()

    def render(self, prompt_id: str, **context: object) -> RenderedPrompt:
        """Render one of this role's prompt templates."""
        return self._prompts.render(prompt_id, **context)

    def start_turn(self, *, round_number: int, prompt: RenderedPrompt) -> Turn:
        """Open a turn record. Closed by `finish_turn`."""
        return Turn(
            round_number=round_number,
            role=self.role,
            model_id=self._config.model_id,
            prompt_id=prompt.prompt_id,
            prompt_hash=prompt.rendered_hash,
        )

    def finish_turn(self, turn: Turn, response: ModelResponse) -> Turn:
        """Close a turn with the response metadata."""
        turn.completed_at = datetime.now(UTC)
        turn.raw_response = response.content
        turn.prompt_tokens = response.prompt_tokens
        turn.completion_tokens = response.completion_tokens
        return turn

    def ground_arguments(self, arguments: list[Argument]) -> list[Argument]:
        """Resolve every citation on every argument, in place."""
        for arg in arguments:
            arg.resolved_citations = self._resolver.resolve_all(arg.citations)
            if not arg.is_grounded and arg.citations:
                log.warning(
                    "argument_ungrounded",
                    role=self.role.value,
                    argument_id=arg.id,
                    citations=[c.locator() for c in arg.citations],
                )
        return arguments

    def ground_objections(self, objections: list[Objection]) -> list[Objection]:
        """Resolve every citation on every objection, in place."""
        for obj in objections:
            obj.resolved_citations = self._resolver.resolve_all(obj.citations)
        return objections
