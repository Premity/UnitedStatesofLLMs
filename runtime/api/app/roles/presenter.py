"""The presenter — argues the position under examination."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from app.roles.base import BaseRole
from council_core.models.citation import ResolvedCitation, malformed_citations
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    Role,
    Turn,
)

#: A retrieved span longer than this is trimmed in the rebuttal. Article-level
#: chunks of long articles are the only spans this size: Rome Statute art. 8
#: is about 10,400 characters (about 2,000 tokens), and the next largest span
#: in the core cases is about 2,600 characters.
REBUTTAL_SPAN_CHAR_LIMIT = 4000


def rebuttal_context(
    context: list[ResolvedCitation],
    prior_arguments: list[Argument],
    prior_objections: list[Objection],
) -> list[ResolvedCitation]:
    """The retrieved context for a rebuttal, with whole long articles cut to what was cited.

    The rebuttal prompt repeats the whole context plus every argument and
    objection so far, and on Groq's free tier the presenter's model refuses a
    request over 8,000 tokens a minute: the full council's round 2 on Galić was
    refused at 8,278. Most of that is one span, the whole of Rome Statute
    art. 8, retrieved alongside the sub-provisions that are actually argued.

    A span over `REBUTTAL_SPAN_CHAR_LIMIT` is kept whole if an earlier round
    cited it as a whole. Otherwise it is replaced by the provisions inside it
    that earlier rounds cited, with their text from the index, and dropped if
    none were. Shorter spans and their order are unchanged, so the rebuttal
    still quotes from the same sources the debate has been arguing about; what
    it loses is the uncited remainder of a long article.
    """
    cited = [
        rc
        for item in [*prior_arguments, *prior_objections]
        for rc in item.resolved_citations
        if rc.corpus_text
    ]
    cited_locators = {rc.citation.locator() for rc in cited}
    shown = {span.citation.locator() for span in context}

    trimmed: list[ResolvedCitation] = []
    for span in context:
        locator = span.citation.locator()
        if len(span.corpus_text or "") <= REBUTTAL_SPAN_CHAR_LIMIT or locator in cited_locators:
            trimmed.append(span)
            continue
        for rc in cited:
            inner = rc.citation.locator()
            if inner.startswith(f"{locator}(") and inner not in shown:
                trimmed.append(rc)
                shown.add(inner)
    return trimmed


class _PresenterResponse(BaseModel):
    """Schema the presenter must return."""

    arguments: list[Argument]

    @model_validator(mode="after")
    def _citations_are_well_formed(self) -> _PresenterResponse:
        # A malformed citation goes back to the model through the repair prompt
        # instead of reaching the resolver as an "unresolved" fabrication.
        problem = malformed_citations(
            [(f"arguments[{i}]", item.citations) for i, item in enumerate(self.arguments)]
        )
        if problem:
            raise ValueError(problem)
        return self


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
            context=(
                context
                if round_number == 1
                else rebuttal_context(context, prior_arguments, prior_objections)
            ),
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
