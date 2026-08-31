"""The presenter — argues the position under examination."""

from __future__ import annotations

from pydantic import BaseModel

from app.roles.base import BaseRole
from council_core.models.citation import ResolvedCitation
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    Role,
    Turn,
)


class _PresenterResponse(BaseModel):
    """Schema the presenter must return."""

    arguments: list[Argument]


class PresenterRole(BaseRole):
    """Builds the case, then defends it against objections in later rounds."""

    role = Role.PRESENTER

    async def run(
        self,
        *,
        config: DebateConfig,
        context: list[ResolvedCitation],
        prior_arguments: list[Argument],
        prior_objections: list[Objection],
        round_number: int,
    ) -> Turn:
        """Produce this round's arguments.

        Round 1 opens the case. Later rounds rebut, so the prompt carries the
        objections raised so far and the arguments they targeted.
        """
        prompt_id = "presenter/opening" if round_number == 1 else "presenter/rebuttal"

        prompt = self.render(
            prompt_id,
            question=config.question,
            facts=config.facts,
            context=context,
            prior_arguments=prior_arguments,
            prior_objections=prior_objections,
            round_number=round_number,
        )

        turn = self.start_turn(round_number=round_number, prompt=prompt)
        parsed, response = await self._llm.complete_structured(
            system=prompt.system,
            user=prompt.user,
            schema=_PresenterResponse,
            seed=self._models.seed,
        )

        turn.arguments = self.ground_arguments(parsed.arguments)
        return self.finish_turn(turn, response)
