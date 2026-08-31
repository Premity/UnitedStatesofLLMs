"""Calibration metrics.

The project's sharpest claim is not that the council is more often right — it is
that the council is *appropriately uncertain* where a single pass is confidently
wrong. That claim lives or dies on these numbers.

A system that answers 70% of contested questions correctly while reporting 70%
confidence is well calibrated. One that answers 70% correctly while reporting
95% confidence is overconfident, and in this domain that is the dangerous
failure — it is what makes a fluent wrong answer persuasive.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np


@dataclass(frozen=True)
class CalibrationResult:
    """Calibration summary for one arm."""

    brier_score: float
    """Mean squared error of the confidence against the outcome. Lower is better;
    0.25 is what you get by always answering 0.5."""

    expected_calibration_error: float
    """Mean gap between confidence and accuracy, bucketed. Lower is better."""

    mean_confidence: float
    accuracy: float

    overconfidence: float
    """mean_confidence - accuracy. Positive means the system claims more certainty
    than it earns. This is the headline number for the project's argument."""

    n: int


def brier_score(confidences: list[float], correct: list[bool]) -> float:
    """Mean squared error between stated confidence and outcome."""
    if not confidences:
        return float("nan")
    conf = np.asarray(confidences, dtype=float)
    truth = np.asarray(correct, dtype=float)
    return float(np.mean((conf - truth) ** 2))


def expected_calibration_error(
    confidences: list[float],
    correct: list[bool],
    *,
    n_bins: int = 10,
) -> float:
    """Bucketed gap between confidence and accuracy.

    Confidences are binned; within each bin the mean confidence is compared to
    the observed accuracy, and the gaps are averaged weighted by bin size.

    With a small case set most bins will be empty or near-empty — report this
    alongside the Brier score rather than instead of it.
    """
    if not confidences:
        return float("nan")

    conf = np.asarray(confidences, dtype=float)
    truth = np.asarray(correct, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)

    total = 0.0
    for lo, hi in pairwise(edges):
        # Upper-inclusive on the final bin so confidence 1.0 is counted.
        in_bin = (conf > lo) & (conf <= hi) if hi < 1.0 else (conf > lo) & (conf <= 1.0)
        if not in_bin.any():
            continue
        weight = in_bin.mean()
        total += weight * abs(truth[in_bin].mean() - conf[in_bin].mean())

    return float(total)


def evaluate_calibration(
    confidences: list[float],
    correct: list[bool],
    *,
    n_bins: int = 10,
) -> CalibrationResult:
    """Compute the full calibration summary for one arm."""
    accuracy = float(np.mean(correct)) if correct else float("nan")
    mean_conf = float(np.mean(confidences)) if confidences else float("nan")

    return CalibrationResult(
        brier_score=brier_score(confidences, correct),
        expected_calibration_error=expected_calibration_error(confidences, correct, n_bins=n_bins),
        mean_confidence=mean_conf,
        accuracy=accuracy,
        overconfidence=mean_conf - accuracy,
        n=len(confidences),
    )


def bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval.

    With 40-80 cases, differences between arms carry wide intervals. Report them.
    A three-point gap with overlapping intervals is not a result, and presenting
    it as one is the easiest way to lose credibility on this project.
    """
    if not values:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = rng.choice(arr, size=(n_resamples, arr.size), replace=True).mean(axis=1)

    return (
        float(np.percentile(means, 100 * alpha / 2)),
        float(np.percentile(means, 100 * (1 - alpha / 2))),
    )
