"""Reasoning overlap: did a run rest on the grounds the tribunal relied on?

Scored by hand against each case's `key_reasoning` (GitHub #27). The rubric is
in docs/evaluation.md, section 5. This module loads and checks the scores; it
does not produce them. A model scoring models would put the thing under test
into its own measurement, and at three cases there is no hand-scored set left
over to validate one against.

A score is keyed by `run_id`, not by case and arm: re-running a case produces
a new run that nobody has read, and it must show as unscored rather than
inherit the old run's score.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Annotated, Any

from pydantic import BaseModel, Field

from council_core.models.case import Case

#: Bump when the rubric's meaning changes. Scores recorded under another
#: version are refused rather than silently mixed with new ones.
RUBRIC_VERSION = 1

#: Points per `key_reasoning` entry. The rubric defines each value.
MAX_POINT = 2

EVALUATION_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCORES_PATH = EVALUATION_DIR / "scores" / "reasoning_overlap.json"
DEFAULT_CASES_DIR = EVALUATION_DIR / "cases"

Point = Annotated[int, Field(ge=0, le=MAX_POINT)]


class OverlapScore(BaseModel):
    """One scorer's reading of one run, one point per `key_reasoning` entry."""

    case_id: str
    arm: str
    run_id: str
    scorer: str = Field(min_length=1, description="A short label; it is public.")
    points: list[Point] = Field(min_length=1)
    notes: str = ""

    @property
    def score(self) -> float:
        """Share of the available points, 0.0 to 1.0."""
        return sum(self.points) / (MAX_POINT * len(self.points))


class ScoresFile(BaseModel):
    rubric_version: int
    scores: list[OverlapScore] = Field(default_factory=list)


def key_reasoning_counts(cases_dir: Path = DEFAULT_CASES_DIR) -> dict[str, int]:
    """How many `key_reasoning` entries each case has, across dev and held-out."""
    counts: dict[str, int] = {}
    for path in sorted(cases_dir.glob("*/*.json")):
        case = Case.model_validate(json.loads(path.read_text(encoding="utf-8")))
        counts[case.id] = len(case.key_reasoning)
    return counts


def load_scores(
    path: Path = DEFAULT_SCORES_PATH,
    *,
    cases_dir: Path = DEFAULT_CASES_DIR,
) -> list[OverlapScore]:
    """Read and check the scores file. A missing file means nothing is scored yet."""
    if not path.exists():
        return []
    data = ScoresFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if data.rubric_version != RUBRIC_VERSION:
        raise ValueError(
            f"{path} was scored under rubric version {data.rubric_version}, but the "
            f"rubric is now version {RUBRIC_VERSION}. Rescore, or keep the old file apart."
        )
    validate_scores(data.scores, key_reasoning_counts(cases_dir))
    return data.scores


def validate_scores(scores: Iterable[OverlapScore], counts: Mapping[str, int]) -> None:
    """One point per `key_reasoning` entry, one score per run per scorer."""
    seen: set[tuple[str, str]] = set()
    for score in scores:
        where = f"run {score.run_id} (scorer {score.scorer})"
        if score.case_id not in counts:
            raise ValueError(f"{where}: unknown case {score.case_id!r}")
        if len(score.points) != counts[score.case_id]:
            raise ValueError(
                f"{where}: {len(score.points)} points, but {score.case_id} has "
                f"{counts[score.case_id]} key_reasoning entries"
            )
        key = (score.run_id, score.scorer)
        if key in seen:
            raise ValueError(f"{where}: scored twice")
        seen.add(key)


def scores_by_run(scores: Iterable[OverlapScore]) -> dict[str, list[OverlapScore]]:
    grouped: dict[str, list[OverlapScore]] = defaultdict(list)
    for score in scores:
        grouped[score.run_id].append(score)
    return dict(grouped)


def run_overlap(scores: list[OverlapScore]) -> float | None:
    """A run's overlap: the mean across its scorers. Disagreement is reported, not hidden."""
    return mean(score.score for score in scores) if scores else None


def match_to_results(
    scores: Iterable[OverlapScore], results: Iterable[Mapping[str, Any]]
) -> tuple[dict[str, list[OverlapScore]], list[OverlapScore]]:
    """Attach scores to the results they read; return the ones with no result.

    A score naming a run whose case or arm differs is an error in the scores
    file, not a mismatch to shrug off.
    """
    by_run = {str(r["run_id"]): r for r in results if r.get("run_id")}
    matched: dict[str, list[OverlapScore]] = defaultdict(list)
    unmatched: list[OverlapScore] = []
    for score in scores:
        result = by_run.get(score.run_id)
        if result is None:
            unmatched.append(score)
            continue
        if (result.get("case_id"), result.get("arm")) != (score.case_id, score.arm):
            raise ValueError(
                f"Score for run {score.run_id} says {score.case_id}/{score.arm}, but that "
                f"run is {result.get('case_id')}/{result.get('arm')}"
            )
        matched[score.run_id].append(score)
    return dict(matched), unmatched


def agreement(scores: Iterable[OverlapScore]) -> tuple[int, int]:
    """Points on which two scorers of the same run gave the same value.

    Returns (agreeing, compared) over every pair of scorers on every run. Exact
    agreement rather than a kappa: with three values and a few dozen points, a
    chance-corrected figure would be precise-looking and unstable.
    """
    agreeing = compared = 0
    for run_scores in scores_by_run(scores).values():
        for first, second in combinations(run_scores, 2):
            pairs = list(zip(first.points, second.points, strict=True))
            compared += len(pairs)
            agreeing += sum(1 for a, b in pairs if a == b)
    return agreeing, compared
