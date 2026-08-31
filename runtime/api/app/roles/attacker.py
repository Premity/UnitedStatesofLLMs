"""The attackers — challenge the presenter's case.

One class, two instances. The mandate difference lives entirely in the prompt
template and the model assignment, which keeps the ablation arms honest: turning
off one attacker changes nothing about how the other behaves.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.roles.base import BaseRole
from council_core.models.citation import ResolvedCitation
from council_core.models.debate import Argument, DebateConfig, Objection, Role, Turn

_PROMPT_BY_ROLE = {
    Role.ATTACKER_DOCTRINAL: "attacker_doctrinal/challenge",
    Role.ATTACKER_EVIDENTIARY: "attacker_evidentiary/challenge",
}


class _AttackerResponse(BaseModel):
    """Schema an attacker must return."""

    objections: list[Objection]


class AttackerRole(BaseRole):
    """Raises objections against specific arguments."""

    def __init__(self, role: Role) -> None:
        if role not in _PROMPT_BY_ROLE:
            raise ValueError(f"{role} is not an attacker role.")
        super().__init__(role)

    async def run(
        self,
        *,
        config: DebateConfig,
        context: list[ResolvedCitation],
        arguments: list[Argument],
        round_number: int,
    ) -> Turn:
        """Raise objections against the current arguments."""
        prompt = self.render(
            _PROMPT_BY_ROLE[self.role],
            question=config.question,
            facts=config.facts,
            context=context,
            arguments=arguments,
            round_number=round_number,
        )

        turn = self.start_turn(round_number=round_number, prompt=prompt)
        parsed, response = await self._llm.complete_structured(
            system=prompt.system,
            user=prompt.user,
            schema=_AttackerResponse,
            seed=self._models.seed,
        )

        # The model names its own role in the response; overwrite it with the
        # truth so an attacker cannot attribute objections to its counterpart.
        for obj in parsed.objections:
            obj.raised_by = self.role

        turn.objections = self.ground_objections(parsed.objections)
        return self.finish_turn(turn, response)
