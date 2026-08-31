"""The judge — rules on objections and produces the verdict.

Two things distinguish this role from a summariser:

1. Every objection must receive a disposition *and a stated reason*. The
   overruled ones become the dissent log, and a dissent entry without a reason
   is useless to a reviewer.
2. The confidence is required to come with its own justification. Asking a model
   for a bare number invites 0.85 on everything; asking it to explain the number
   is what makes calibration measurable.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from app.roles.base import BaseRole
from council_core.models.citation import ResolvedCitation
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    ObjectionDisposition,
    Role,
    Turn,
    Verdict,
)

log = structlog.get_logger(__name__)


class _Ruling(BaseModel):
    """The judge's disposition of a single objection."""

    objection_id: str
    disposition: ObjectionDisposition
    reasoning: str = Field(description="Why. Required — this is the dissent log entry.")


class _JudgeResponse(BaseModel):
    """Schema the judge must return."""

    conclusion: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reasoning: str = ""
    rulings: list[_Ruling] = Field(default_factory=list)
    surviving_argument_ids: list[str] = Field(default_factory=list)
    novel_objections_raised: bool = Field(
        default=True,
        description=(
            "Whether this round raised objections materially different from earlier "
            "rounds. False lets an 'auto' debate terminate."
        ),
    )


class JudgeRole(BaseRole):
    """Synthesises the debate into a reasoned, calibrated conclusion."""

    role = Role.JUDGE

    async def run(
        self,
        *,
        config: DebateConfig,
        context: list[ResolvedCitation],
        arguments: list[Argument],
        objections: list[Objection],
        round_number: int,
    ) -> tuple[Turn, Verdict, bool]:
        """Rule on the round.

        Returns:
            The turn record, the verdict, and whether novel objections were
            raised (which drives early termination in `auto` mode).
        """
        prompt = self.render(
            "judge/rule",
            question=config.question,
            facts=config.facts,
            context=context,
            arguments=arguments,
            objections=objections,
            round_number=round_number,
            max_rounds=config.max_rounds,
        )

        turn = self.start_turn(round_number=round_number, prompt=prompt)
        parsed, response = await self._llm.complete_structured(
            system=prompt.system,
            user=prompt.user,
            schema=_JudgeResponse,
            seed=self._models.seed,
        )

        by_id = {o.id: o for o in objections}
        for ruling in parsed.rulings:
            objection = by_id.get(ruling.objection_id)
            if objection is None:
                log.warning("ruling_on_unknown_objection", objection_id=ruling.objection_id)
                continue
            objection.disposition = ruling.disposition
            objection.disposition_reasoning = ruling.reasoning

        verdict = Verdict(
            conclusion=parsed.conclusion,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
            confidence_reasoning=parsed.confidence_reasoning,
            surviving_argument_ids=parsed.surviving_argument_ids,
            dissent=[o for o in objections if o.disposition == ObjectionDisposition.OVERRULED],
        )

        return self.finish_turn(turn, response), verdict, parsed.novel_objections_raised
