"""The debate itself: roles, turns, arguments, objections, and the verdict.

`DebateState` is the object every LangGraph node reads and writes. When a run
finishes, that same object *is* the dissent log — the record of what was argued,
what was objected to, and which objections the judge overruled. Nothing is
reconstructed after the fact.

See `docs/architecture.md` for the graph shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, Field

from council_core.models.citation import Citation, ResolvedCitation


class Role(StrEnum):
    """The four seats at the council, plus the retrieval role.

    Roles are separated by *mandate*, not only by capability. The two attackers
    exist to challenge different things, which is what makes their objections
    independent enough to be worth having both.
    """

    PRESENTER = "presenter"
    """Argues the position. Sets the quality ceiling for the whole debate."""

    ATTACKER_DOCTRINAL = "attacker_doctrinal"
    """Challenges the legal characterisation: proportionality, distinction,
    command responsibility, elements of the crime."""

    ATTACKER_EVIDENTIARY = "attacker_evidentiary"
    """Challenges the factual predicate: sufficiency of evidence, inference of
    mens rea, attribution."""

    JUDGE = "judge"
    """Synthesises surviving arguments, rules on each objection, and calibrates
    the final confidence."""

    RETRIEVER = "retriever"
    """Not a debater. Grounds the others against the corpus."""


class ObjectionDisposition(StrEnum):
    """How the judge ruled on an objection.

    `OVERRULED` objections are the substance of the dissent log — the judge
    rejected them, and the record must show what was rejected and why.
    """

    SUSTAINED = "sustained"
    """The objection defeated or materially weakened the argument."""

    OVERRULED = "overruled"
    """The judge rejected the objection. Recorded in the dissent log."""

    PARTIAL = "partial"
    """The objection narrowed the argument without defeating it."""

    UNADDRESSED = "unaddressed"
    """The judge did not reach it. A gap worth surfacing, not hiding."""


class Argument(BaseModel):
    """A single load-bearing proposition advanced by the presenter."""

    id: str = Field(default_factory=lambda: f"arg_{uuid4().hex[:8]}")
    claim: str = Field(description="The proposition, stated in one sentence.")
    reasoning: str = Field(description="Why the claim follows from the authority cited.")
    citations: list[Citation] = Field(default_factory=list)
    resolved_citations: list[ResolvedCitation] = Field(
        default_factory=list,
        description="Populated by the citation validator after the turn completes.",
    )

    @property
    def is_grounded(self) -> bool:
        """True when the argument cites at least one authority that resolved.

        An argument with no resolvable citation is not necessarily wrong, but it
        is unsupported by the corpus and the judge is told so.
        """
        return any(rc.is_supported for rc in self.resolved_citations)


class Objection(BaseModel):
    """A challenge raised by one of the attackers against a specific argument."""

    id: str = Field(default_factory=lambda: f"obj_{uuid4().hex[:8]}")
    raised_by: Role
    target_argument_id: str = Field(description="The `Argument.id` under challenge.")
    ground: str = Field(description="The basis of the objection, in one sentence.")
    reasoning: str
    citations: list[Citation] = Field(default_factory=list)
    resolved_citations: list[ResolvedCitation] = Field(default_factory=list)

    disposition: ObjectionDisposition = ObjectionDisposition.UNADDRESSED
    disposition_reasoning: str | None = Field(
        default=None,
        description="The judge's stated reason for the ruling. Required for the dissent log.",
    )


class Turn(BaseModel):
    """One model invocation and everything it produced.

    Turns are the unit the frontend streams and the unit the run artifact
    records. Token counts and latency come from LiteLLM's response metadata.
    """

    id: str = Field(default_factory=lambda: f"turn_{uuid4().hex[:8]}")
    round_number: int
    role: Role
    model_id: str = Field(description="Fully qualified LiteLLM model id actually used.")
    prompt_id: str = Field(description="Prompt template id, e.g. 'presenter/opening'.")
    prompt_hash: str = Field(description="SHA-256 of the rendered prompt, for reproducibility.")

    arguments: list[Argument] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    raw_response: str = Field(default="", description="Unparsed model output, kept verbatim.")

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None


class Verdict(BaseModel):
    """The judge's ruling, with calibrated confidence and the dissent log."""

    conclusion: str = Field(description="The holding, stated plainly.")
    reasoning: str = Field(description="How the surviving arguments support it.")

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Calibrated probability the conclusion is correct. Scored against "
            "tribunal outcomes via Brier score in the evaluation harness."
        ),
    )
    confidence_reasoning: str = Field(
        default="",
        description="Why the confidence is where it is. Guards against unexamined certainty.",
    )

    surviving_argument_ids: list[str] = Field(default_factory=list)
    dissent: list[Objection] = Field(
        default_factory=list,
        description=(
            "The overruled objections — the framework's headline output. Each carries "
            "the judge's stated reason for rejecting it."
        ),
    )


class DebateConfig(BaseModel):
    """User-facing knobs for a single run.

    `max_rounds` is a hard ceiling in every mode, including `auto`. A debate that
    cannot terminate is a bug, not a feature.
    """

    question: str = Field(description="The legal question put to the council.")
    facts: str = Field(default="", description="The factual predicate, as given.")

    rounds: int | Annotated[str, "auto"] = Field(
        default="auto",
        description=(
            "Fixed number of rounds, or 'auto' to let the judge stop once the "
            "attackers raise no novel objections. Always bounded by max_rounds."
        ),
    )
    max_rounds: int = Field(default=3, ge=1, le=5, description="Hard upper bound.")

    enabled_attackers: list[Role] = Field(
        default_factory=lambda: [Role.ATTACKER_DOCTRINAL, Role.ATTACKER_EVIDENTIARY],
        description="Which attackers sit. Ablation arms vary this.",
    )
    retrieval_enabled: bool = Field(default=True, description="False for the ungrounded arm.")
    top_k: int = Field(default=8, ge=1, le=50, description="Corpus chunks retrieved per query.")


class DebateState(BaseModel):
    """The LangGraph state object — and, once complete, the dissent log itself.

    IMPORTANT (learned the hard way in a prior project): parallel nodes must
    return only the keys they write, never the whole state. The two attackers
    run concurrently and both append to `turns`; each returns a partial update
    and the reducer merges them. Returning the full state from a parallel node
    raises `InvalidUpdateError`.
    """

    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    config: DebateConfig

    context: list[ResolvedCitation] = Field(
        default_factory=list,
        description="Corpus spans retrieved for this question, shared by all roles.",
    )

    current_round: int = 0
    turns: list[Turn] = Field(default_factory=list)
    arguments: list[Argument] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)

    verdict: Verdict | None = None
    terminated_reason: str | None = Field(
        default=None,
        description="Why the debate stopped: 'max_rounds', 'no_novel_objections', or 'error'.",
    )

    def objections_for(self, argument_id: str) -> list[Objection]:
        """Every objection raised against one argument, across all rounds."""
        return [o for o in self.objections if o.target_argument_id == argument_id]

    def objections_by(self, role: Role) -> list[Objection]:
        """Every objection raised by one attacker.

        Used by the attacker-independence metric, which measures overlap between
        the two attackers' objection sets.
        """
        return [o for o in self.objections if o.raised_by == role]
