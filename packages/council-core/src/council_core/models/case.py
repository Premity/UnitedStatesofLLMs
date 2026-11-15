"""An adjudicated question with a known outcome.

A case is where a tribunal's holding supplies the ground truth. The system sees
`question` and `facts`; it never sees `holding`, which is what makes outcome
agreement a real measurement rather than a leak.

The schema lives here, not in `evaluation/`, so the API can parse a case file
without depending on the harness (ADR 0013). Anything that leaves the machine
goes through `Case.public()`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    """Ternary outcome, matching how the judge may conclude."""

    AFFIRMED = "affirmed"
    """The tribunal held that the conduct did constitute the violation."""

    REJECTED = "rejected"
    """The tribunal held that it did not."""

    INDETERMINATE = "indeterminate"
    """The tribunal did not resolve it, or resolved it on other grounds."""


class PublicCase(BaseModel):
    """The part of a case that may be shown to a person choosing a question.

    A separate model rather than a filtered dump of `Case`: a field added to
    `Case` later stays out of this one until someone adds it here on purpose.
    """

    id: str
    title: str
    court: str
    year: int
    question: str
    facts: str
    difficulty: str


class Case(BaseModel):
    """One adjudicated question with a known outcome."""

    id: str
    title: str
    court: str
    year: int

    question: str = Field(description="Shown to the system.")
    facts: str = Field(description="Shown to the system. Facts as the tribunal found them.")

    holding: str = Field(description="Ground truth. NEVER shown to the system.")
    outcome: Outcome = Field(description="Ground truth, for outcome agreement scoring.")
    key_reasoning: list[str] = Field(
        default_factory=list,
        description=(
            "The grounds the tribunal actually relied on. Used to score whether the "
            "system anticipated the tribunal's reasoning, not merely its result."
        ),
    )

    difficulty: str = Field(
        default="medium",
        description="'settled', 'medium', or 'contested'. Contested cases are where "
        "calibration matters most — a well-calibrated system should be less certain there.",
    )
    source_case_id: str | None = Field(
        default=None,
        description="Corpus case id, if the judgment is indexed. Excluded from retrieval "
        "during evaluation so the system cannot simply read the answer.",
    )

    def public(self) -> PublicCase:
        """The fields safe to send to a browser. Never includes ground truth."""
        return PublicCase(
            id=self.id,
            title=self.title,
            court=self.court,
            year=self.year,
            question=self.question,
            facts=self.facts,
            difficulty=self.difficulty,
        )
