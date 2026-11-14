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

CORE_CASE_IDS: tuple[str, ...] = (
    "icty_galic_terror",
    "icty_gotovina_knin",
    "icc_bemba_command",
)
"""The scored evaluation (ADR 0012): both question families, both outcomes, both courts."""

STRETCH_CASE_IDS: tuple[str, ...] = (
    "icty_martic_zagreb",
    "icty_strugar_dubrovnik",
    "icty_mrksic_vukovar",
)
"""Run only with judge quota left after the core cases, in this order (ADR 0012).

The medium-difficulty cases, to balance a core set that is two-thirds hard. A
stretch case counts only once all five arms have completed on it.
"""

TIERS: dict[str, tuple[str, ...]] = {
    "core": CORE_CASE_IDS,
    "stretch": STRETCH_CASE_IDS,
    "all": CORE_CASE_IDS + STRETCH_CASE_IDS,
}


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


def select_cases(
    cases: list[EvaluationCase],
    *,
    tier: str = "core",
    case_ids: list[str] | None = None,
) -> list[EvaluationCase]:
    """Pick the cases a run should use, in the tier's order.

    Args:
        cases: The loaded fixtures.
        tier: `core`, `stretch` or `all` (see `TIERS`).
        case_ids: If given, narrow the tier to these ids. Each must be in the
            tier, so a typo or a case outside the scope fails loudly instead of
            silently running nothing.

    Raises:
        ValueError: on an unknown tier, a case id outside the tier, or a tier
            id with no fixture on disk.
    """
    if tier not in TIERS:
        raise ValueError(f"Unknown tier '{tier}'. Expected one of: {', '.join(TIERS)}.")
    wanted = TIERS[tier]
    if case_ids:
        outside = [case_id for case_id in case_ids if case_id not in wanted]
        if outside:
            raise ValueError(f"Not in tier '{tier}': {', '.join(outside)}.")
        wanted = tuple(case_id for case_id in wanted if case_id in case_ids)

    by_id = {case.id: case for case in cases}
    missing = [case_id for case_id in wanted if case_id not in by_id]
    if missing:
        raise ValueError(f"No fixture for: {', '.join(missing)}.")
    return [by_id[case_id] for case_id in wanted]
