"""Tests for the evaluation Markdown report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.report import generate_report, render_report


def _result(
    *,
    arm: str,
    correct: bool,
    confidence: float,
    unresolved: int = 0,
    out_of_corpus: int = 0,
    backend: str = "api",
    synthetic: bool = False,
) -> dict:
    return {
        "arm": arm,
        "judge_backend": "mock" if synthetic else backend,
        "synthetic": synthetic,
        "ground_truth_outcome": "affirmed",
        "predicted_outcome": "affirmed" if correct else "rejected",
        "outcome_correct": correct,
        "confidence": confidence,
        "objections": [],
        "citation_statuses": {
            "total": unresolved + out_of_corpus + 2,
            "unresolved": unresolved,
            "out_of_corpus": out_of_corpus,
            "resolved": 2,
            "misquoted": 0,
        },
        "prompt_hashes": {"judge/rule.md": "hash-123"},
    }


def test_report_calculates_metrics_and_discloses_provenance(tmp_path: Path) -> None:
    results = [
        _result(arm="rag", correct=True, confidence=0.8, unresolved=1, out_of_corpus=8),
        _result(arm="rag", correct=False, confidence=0.9),
    ]
    result_dir = tmp_path / "eval"
    (result_dir / "rag").mkdir(parents=True)
    for index, result in enumerate(results):
        (result_dir / "rag" / f"case-{index}.json").write_text(json.dumps(result), encoding="utf-8")

    output = generate_report(results_dir=result_dir, output_path=tmp_path / "report.md")
    report = output.read_text(encoding="utf-8")

    assert "Accuracy" in report
    assert "Brier" in report
    assert "ECE" in report
    assert "Overconfidence" in report
    assert "Citation fabrication rate" in report
    assert "Attacker independence" in report
    assert "api" in report
    assert "judge/rule.md" in report
    assert "hash-123" in report
    assert "unresolved / (total citations - out_of_corpus)" in report
    summary = next(line for line in report.splitlines() if line.startswith("| rag |"))
    assert "0.333" in summary
    assert "percentile 95% confidence intervals" in report


def test_report_refuses_synthetic_results_unless_explicitly_allowed() -> None:
    synthetic = [_result(arm="rag", correct=True, confidence=0.9, synthetic=True)]

    with pytest.raises(ValueError, match="Synthetic results are not scored"):
        render_report(synthetic)

    report = render_report(synthetic, allow_mixed_results=True)
    assert "## Synthetic (not scored)" in report
    assert "## Real results" not in report


def test_report_keeps_explicitly_allowed_provenance_groups_separate() -> None:
    report = render_report(
        [
            _result(arm="rag", correct=True, confidence=0.9),
            _result(arm="rag", correct=False, confidence=0.9, synthetic=True),
        ],
        allow_mixed_results=True,
    )

    assert "## Real results" in report
    assert "## Synthetic (not scored)" in report


def test_report_counts_errors_separately_and_excludes_them_from_metrics() -> None:
    completed_correct = _result(arm="rag", correct=True, confidence=0.8)
    completed_wrong = _result(arm="rag", correct=False, confidence=0.9)
    errored = _result(arm="rag", correct=False, confidence=0.99)
    errored.update(
        status="error",
        error_type="error",
        outcome_correct=None,
        confidence=None,
    )
    timed_out = _result(arm="rag", correct=False, confidence=0.99)
    timed_out.update(
        status="error",
        error_type="timeout",
        outcome_correct=None,
        confidence=None,
    )

    report = render_report([completed_correct, completed_wrong, errored, timed_out])

    summary = next(line for line in report.splitlines() if line.startswith("| rag |"))
    assert "| rag | 4 | 2 | 1 | 1 | 1 |" in summary
    assert "0.500 (n=2)" in summary
    assert "0.425 (n=2)" in summary
    assert "0.550 (n=2)" in summary
    assert "n=2" in summary
    assert "fewer than 5 completed cases" in report
