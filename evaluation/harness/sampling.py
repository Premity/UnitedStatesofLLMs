"""Self-consistency sampling and aggregation machinery for Arm E (ADR 0011).

Arm E controls for compute expenditure by sampling the presenter n times with
retrieval grounding, aggregating the samples via majority vote, and passing the
aggregate to the judge once.

The sample count n is derived per-case from Arm D's actual model calls on the same
case, ensuring that total model invocations match Arm D within ±1.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from council_core.models.debate import Argument, Turn

if TYPE_CHECKING:
    from council_core.models.debate import DebateState

DEFAULT_SAMPLING_TEMPERATURE: float = 0.7
"""Sampling temperature providing semantic variation while preserving schema adherence."""


def derive_sample_count(d_calls: int, *, has_judge: bool = True) -> int:
    """Derive presenter sample count n from Arm D's total model calls on the same case.

    In Arm E, the presenter is sampled n times at elevated temperature. If has_judge
    is True, the judge executes once over the aggregated answer (1 call).
    To equate total compute to Arm D:
        total_calls(E) = n + 1 (with judge)
        total_calls(D) = d_calls
        n = max(1, d_calls - 1)

    This guarantees that total model calls match Arm D within ±1 across all cases.
    """
    if d_calls <= 0:
        raise ValueError(f"Arm D call count must be positive, got {d_calls}")
    if has_judge:
        return max(1, d_calls - 1)
    return max(1, d_calls)


def total_calls_for_arm_e(samples: int, *, has_judge: bool = True) -> int:
    """Compute total model calls Arm E executes given sample count n."""
    if samples <= 0:
        raise ValueError(f"Sample count must be positive, got {samples}")
    return samples + (1 if has_judge else 0)


def derive_sample_count_from_turns(turns: list[Turn], *, has_judge: bool = True) -> int:
    """Derive Arm E sample count directly from Arm D's recorded turns."""
    return derive_sample_count(len(turns), has_judge=has_judge)


def derive_sample_count_from_state(state: DebateState, *, has_judge: bool = True) -> int:
    """Derive Arm E sample count directly from Arm D's final debate state."""
    return derive_sample_count(len(state.turns), has_judge=has_judge)


@dataclass(frozen=True)
class PresenterSample:
    """One candidate presenter generation under self-consistency sampling."""

    sample_id: str
    arguments: list[Argument]
    outcome: str | None = None
    confidence: float | None = None
    raw_response: str = ""


@dataclass(frozen=True)
class AggregationResult:
    """Result of majority-vote aggregation over n self-consistency samples."""

    winning_outcome: str | None
    agreement_rate: float
    """Share of samples backing the winning outcome (empirical confidence)."""

    vote_counts: dict[str, int] = field(default_factory=dict)
    total_samples: int = 0
    aggregated_arguments: list[Argument] = field(default_factory=list)
    selected_sample: PresenterSample | None = None


def aggregate_samples(samples: list[PresenterSample]) -> AggregationResult:
    """Aggregate n presenter samples via majority vote (ADR 0011).

    1. Tally votes for each outcome.
    2. Determine the plurality/majority outcome.
    3. Calculate the agreement rate (count(winning_outcome) / total_samples) as
       the empirical confidence.
    4. Break ties deterministically using the highest summed sample confidence.
    5. Select the representative argument set from the highest-confidence sample
       supporting the winning outcome.
    """
    if not samples:
        raise ValueError("Cannot aggregate an empty list of samples")

    total_samples = len(samples)

    # Normalize outcomes (default to 'indeterminate' if unspecified)
    outcomes = [s.outcome.strip().lower() if s.outcome else "indeterminate" for s in samples]
    counts = Counter(outcomes)

    # Find the maximum vote count
    max_votes = max(counts.values())
    top_candidates = [outcome for outcome, count in counts.items() if count == max_votes]

    # Tie-breaking by confidence, then indeterminate when confidence is equal.
    if len(top_candidates) == 1:
        winning_outcome = top_candidates[0]
    else:
        candidate_scores: dict[str, float] = {}
        for cand in top_candidates:
            cand_samples = [s for s, o in zip(samples, outcomes, strict=True) if o == cand]
            confidence = [s.confidence if s.confidence is not None else 0.5 for s in cand_samples]
            candidate_scores[cand] = sum(confidence) / len(confidence)

        highest_score = max(candidate_scores.values())
        highest_scoring = [
            outcome for outcome in top_candidates if candidate_scores[outcome] == highest_score
        ]
        winning_outcome = highest_scoring[0] if len(highest_scoring) == 1 else "indeterminate"

    agreement_rate = counts[winning_outcome] / total_samples

    # Select the representative sample among those with the winning outcome
    winning_samples = [s for s, o in zip(samples, outcomes, strict=True) if o == winning_outcome]
    if not winning_samples:
        winning_samples = [s for s, o in zip(samples, outcomes, strict=True) if o in top_candidates]
    selected_sample = max(
        winning_samples,
        key=lambda s: s.confidence if s.confidence is not None else 0.5,
    )

    return AggregationResult(
        winning_outcome=winning_outcome,
        agreement_rate=agreement_rate,
        vote_counts=dict(counts),
        total_samples=total_samples,
        aggregated_arguments=list(selected_sample.arguments),
        selected_sample=selected_sample,
    )
