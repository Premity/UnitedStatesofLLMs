"""Tests for calibration metrics (T2-1).

Verifies Brier score, Expected Calibration Error (ECE), overconfidence, and
bootstrap confidence intervals against hand-computed values on standard and
degenerate cases (all-correct, all-wrong, single bin).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from metrics.calibration import (
    CalibrationResult,
    bootstrap_ci,
    brier_score,
    evaluate_calibration,
    expected_calibration_error,
)


class TestCalibrationWorkedExamples:
    """Hand-computed worked examples asserting exact numerical agreement."""

    def test_worked_example_multi_case(self) -> None:
        """Standard 4-case example with mixed confidences and outcomes.

        Cases:
          1. conf = 0.9, correct = True  (gap: 0.9 - 1.0 = -0.1, sq: 0.01)
          2. conf = 0.8, correct = True  (gap: 0.8 - 1.0 = -0.2, sq: 0.04)
          3. conf = 0.6, correct = False (gap: 0.6 - 0.0 =  0.6, sq: 0.36)
          4. conf = 0.7, correct = False (gap: 0.7 - 0.0 =  0.7, sq: 0.49)

        Hand-computations:
          mean_conf   = (0.9 + 0.8 + 0.6 + 0.7) / 4 = 3.0 / 4 = 0.75
          accuracy    = (1 + 1 + 0 + 0) / 4 = 2 / 4 = 0.50
          overconf    = 0.75 - 0.50 = 0.25
          brier_score = (0.01 + 0.04 + 0.36 + 0.49) / 4 = 0.90 / 4 = 0.225

          ECE with n_bins=5 (edges: [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]):
            Bin (0.4, 0.6]: [0.6] -> acc=0.0, conf=0.6, gap=|0.0 - 0.6|=0.6, weight=1/4 -> 0.150
            Bin (0.6, 0.8]: [0.8, 0.7] -> acc=0.5, conf=0.75, gap=|0.5 - 0.75|=0.25, weight=2/4 -> 0.125
            Bin (0.8, 1.0]: [0.9] -> acc=1.0, conf=0.9, gap=|1.0 - 0.9|=0.1, weight=1/4 -> 0.025
            ECE = 0.150 + 0.125 + 0.025 = 0.300
        """
        confidences = [0.9, 0.8, 0.6, 0.7]
        correct = [True, True, False, False]

        brier = brier_score(confidences, correct)
        ece = expected_calibration_error(confidences, correct, n_bins=5)
        result = evaluate_calibration(confidences, correct, n_bins=5)

        assert isinstance(result, CalibrationResult)
        assert pytest.approx(brier, abs=1e-6) == 0.225
        assert pytest.approx(ece, abs=1e-6) == 0.300
        assert pytest.approx(result.mean_confidence, abs=1e-6) == 0.75
        assert pytest.approx(result.accuracy, abs=1e-6) == 0.50
        assert pytest.approx(result.overconfidence, abs=1e-6) == 0.25
        assert result.n == 4
        assert result.brier_score == brier
        assert result.expected_calibration_error == ece

    def test_worked_example_three_bins(self) -> None:
        """Hand-computed 3-case example across distinct 10-bin intervals.

        Cases:
          1. conf = 0.15, correct = False (bin (0.1, 0.2]: acc=0.0, conf=0.15, gap=0.15, w=1/3)
          2. conf = 0.45, correct = True  (bin (0.4, 0.5]: acc=1.0, conf=0.45, gap=0.55, w=1/3)
          3. conf = 0.85, correct = True  (bin (0.8, 0.9]: acc=1.0, conf=0.85, gap=0.15, w=1/3)

        Hand-computations:
          mean_conf   = (0.15 + 0.45 + 0.85) / 3 = 1.45 / 3 = 0.483333333...
          accuracy    = (0 + 1 + 1) / 3 = 2 / 3 = 0.666666666...
          overconf    = 1.45 / 3 - 2 / 3 = -0.55 / 3 = -0.183333333...
          brier_score = (0.15^2 + (0.45 - 1.0)^2 + (0.85 - 1.0)^2) / 3
                      = (0.0225 + 0.3025 + 0.0225) / 3 = 0.3475 / 3 = 0.115833333...
          ECE (n_bins=10) = (0.15 + 0.55 + 0.15) / 3 = 0.85 / 3 = 0.283333333...
        """
        confidences = [0.15, 0.45, 0.85]
        correct = [False, True, True]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        assert pytest.approx(result.brier_score, abs=1e-6) == 0.3475 / 3
        assert pytest.approx(result.expected_calibration_error, abs=1e-6) == 0.85 / 3
        assert pytest.approx(result.mean_confidence, abs=1e-6) == 1.45 / 3
        assert pytest.approx(result.accuracy, abs=1e-6) == 2.0 / 3
        assert pytest.approx(result.overconfidence, abs=1e-6) == -0.55 / 3
        assert result.n == 3


class TestDegenerateCases:
    """Degenerate cases required by T2-1: all-correct, all-wrong, single bin."""

    def test_degenerate_all_correct_perfect_confidence(self) -> None:
        """All-correct with maximum confidence 1.0: zero error, zero overconfidence."""
        confidences = [1.0, 1.0, 1.0]
        correct = [True, True, True]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        assert result.brier_score == 0.0
        assert result.expected_calibration_error == 0.0
        assert result.mean_confidence == 1.0
        assert result.accuracy == 1.0
        assert result.overconfidence == 0.0
        assert result.n == 3

    def test_degenerate_all_correct_underconfident(self) -> None:
        """All-correct with conservative confidence 0.8: negative overconfidence."""
        confidences = [0.8, 0.8]
        correct = [True, True]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        # Brier: (0.8 - 1.0)^2 = 0.04
        assert pytest.approx(result.brier_score, abs=1e-6) == 0.04
        # ECE: single bin (0.7, 0.8], acc=1.0, conf=0.8, gap=0.2
        assert pytest.approx(result.expected_calibration_error, abs=1e-6) == 0.20
        assert result.accuracy == 1.0
        assert result.mean_confidence == 0.8
        assert pytest.approx(result.overconfidence, abs=1e-6) == -0.20

    def test_degenerate_all_wrong_maximum_overconfidence(self) -> None:
        """All-wrong with 1.0 confidence: worst-case Brier, ECE, and overconfidence 1.0."""
        confidences = [1.0, 1.0]
        correct = [False, False]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        assert result.brier_score == 1.0
        assert result.expected_calibration_error == 1.0
        assert result.mean_confidence == 1.0
        assert result.accuracy == 0.0
        assert result.overconfidence == 1.0
        assert result.n == 2

    def test_degenerate_all_wrong_partial_confidence(self) -> None:
        """All-wrong with 0.7 confidence: Brier = 0.49, ECE = 0.7, overconfidence = 0.7."""
        confidences = [0.7, 0.7]
        correct = [False, False]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        assert pytest.approx(result.brier_score, abs=1e-6) == 0.49
        assert pytest.approx(result.expected_calibration_error, abs=1e-6) == 0.70
        assert pytest.approx(result.mean_confidence, abs=1e-6) == 0.70
        assert result.accuracy == 0.0
        assert pytest.approx(result.overconfidence, abs=1e-6) == 0.70

    def test_degenerate_single_bin_well_calibrated(self) -> None:
        """Single bin with matching confidence and empirical accuracy (0.75).

        Four cases with identical confidence 0.75, three correct:
          accuracy = 3/4 = 0.75
          mean_conf = 0.75
          overconfidence = 0.0
          ECE = 0.0
          Brier = (3 * (0.75 - 1.0)^2 + (0.75 - 0.0)^2) / 4
                = (3 * 0.0625 + 0.5625) / 4 = 0.75 / 4 = 0.1875
        """
        confidences = [0.75, 0.75, 0.75, 0.75]
        correct = [True, True, True, False]

        result = evaluate_calibration(confidences, correct, n_bins=10)

        assert pytest.approx(result.brier_score, abs=1e-6) == 0.1875
        assert pytest.approx(result.expected_calibration_error, abs=1e-6) == 0.0
        assert pytest.approx(result.mean_confidence, abs=1e-6) == 0.75
        assert pytest.approx(result.accuracy, abs=1e-6) == 0.75
        assert pytest.approx(result.overconfidence, abs=1e-6) == 0.0
        assert result.n == 4

    def test_degenerate_single_bin_with_gap(self) -> None:
        """Single bin with gap: n_bins=1 over all data points."""
        confidences = [0.6, 0.8]
        correct = [True, False]

        # With n_bins=1, bin is (0.0, 1.0]: both fall inside
        result = evaluate_calibration(confidences, correct, n_bins=1)

        # mean_conf = 0.7, acc = 0.5, gap = 0.2
        assert pytest.approx(result.mean_confidence, abs=1e-6) == 0.7
        assert pytest.approx(result.accuracy, abs=1e-6) == 0.5
        assert pytest.approx(result.overconfidence, abs=1e-6) == 0.2
        assert pytest.approx(result.expected_calibration_error, abs=1e-6) == 0.2
        # Brier: ((0.6 - 1.0)^2 + (0.8 - 0.0)^2) / 2 = (0.16 + 0.64) / 2 = 0.40
        assert pytest.approx(result.brier_score, abs=1e-6) == 0.40


class TestBootstrapConfidenceInterval:
    """Tests for the bootstrap CI calculation."""

    def test_empty_values_return_nan(self) -> None:
        low, high = bootstrap_ci([])
        assert math.isnan(low)
        assert math.isnan(high)

    def test_constant_values_return_constant_interval(self) -> None:
        low, high = bootstrap_ci([0.7, 0.7, 0.7, 0.7], n_resamples=500, seed=42)
        assert pytest.approx(low, abs=1e-6) == 0.7
        assert pytest.approx(high, abs=1e-6) == 0.7

    def test_interval_contains_mean_and_is_bounded(self) -> None:
        values = [0.2, 0.4, 0.6, 0.8, 1.0]
        mean = float(np.mean(values))
        low, high = bootstrap_ci(values, n_resamples=2000, seed=123)

        assert 0.0 <= low <= mean <= high <= 1.0
        assert low < high

    def test_seed_reproducibility(self) -> None:
        values = [0.1, 0.5, 0.9]
        res1 = bootstrap_ci(values, n_resamples=1000, seed=99)
        res2 = bootstrap_ci(values, n_resamples=1000, seed=99)
        assert res1 == res2


class TestCalibrationEdgeCases:
    """Empty and extreme edge cases."""

    def test_empty_inputs_return_nan(self) -> None:
        assert math.isnan(brier_score([], []))
        assert math.isnan(expected_calibration_error([], []))

        result = evaluate_calibration([], [])
        assert math.isnan(result.brier_score)
        assert math.isnan(result.expected_calibration_error)
        assert math.isnan(result.mean_confidence)
        assert math.isnan(result.accuracy)
        assert math.isnan(result.overconfidence)
        assert result.n == 0
