"""Evaluation case fixtures.

A case is an adjudicated question where a tribunal's holding supplies the ground
truth. The system sees `question` and `facts`; it never sees `holding`, which is
what makes outcome agreement a real measurement rather than a leak.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


class Outcome(StrEnum):
    """Ternary outcome, matching how the judge may conclude."""

    AFFIRMED = "affirmed"
    """The tribunal held that the conduct did constitute the violation."""

    REJECTED = "rejected"
    """The tribunal held that it did not."""

    INDETERMINATE = "indeterminate"
    """The tribunal did not resolve it, or resolved it on other grounds."""


class EvaluationCase(BaseModel):
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


def load_cases(*, held_out: bool = False) -> list[EvaluationCase]:
    """Load the case fixtures.

    Args:
        held_out: Load `cases/held_out/` instead of `cases/dev/`. Prompts are
            tuned against dev; the held-out set is scored once, at the end.
            Mixing them invalidates the comparison.
    """
    directory = CASES_DIR / ("held_out" if held_out else "dev")
    cases: list[EvaluationCase] = []

    for path in sorted(directory.glob("*.json")):
        cases.append(EvaluationCase.model_validate(json.loads(path.read_text(encoding="utf-8"))))

    return cases
