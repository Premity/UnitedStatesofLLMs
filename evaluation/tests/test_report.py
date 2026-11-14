"""Tests for the evaluation Markdown report."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from council_core.models.debate import Role
from metrics.report import (
    ARM_ORDER,
    MIN_CASES_FOR_INTERVALS,
    _severity_breakdown,
    generate_report,
    render_report,
)


def _objection(role: Role, ground: str) -> dict:
    return {
        "id": f"{role.value}-1",
        "raised_by": role.value,
        "target_argument_id": "arg-1",
        "ground": ground,
        "reasoning": "-",
    }


def _summary_cells(report: str, arm: str) -> list[str]:
    row = next(line for line in report.splitlines() if line.startswith(f"| {arm} | "))
    return [cell.strip() for cell in row.strip("|").split("|")]


def _case_cells(report: str, case_id: str, arm: str) -> list[str]:
    row = next(
        line
        for line in report.splitlines()
        if line.startswith(f"| {case_id} |") and f"| {arm} |" in line
    )
    return [cell.strip() for cell in row.strip("|").split("|")]


def _result(
    *,
    arm: str,
    correct: bool,
    confidence: float,
    case_id: str = "case-1",
    unresolved: int = 0,
    out_of_corpus: int = 0,
    misquoted: int = 0,
    backend: str = "api",
    synthetic: bool = False,
) -> dict:
    return {
        "case_id": case_id,
        "arm": arm,
        "judge_backend": "mock" if synthetic else backend,
        "synthetic": synthetic,
        "ground_truth_outcome": "affirmed",
        "predicted_outcome": "affirmed" if correct else "rejected",
        "outcome_correct": correct,
        "confidence": confidence,
        "objections": [],
        "citation_statuses": {
            "total": unresolved + out_of_corpus + misquoted + 2,
            "unresolved": unresolved,
            "out_of_corpus": out_of_corpus,
            "resolved": 2,
            "misquoted": misquoted,
        },
        "prompt_hashes": {"judge/rule.md": "hash-123"},
    }


def test_report_calculates_metrics_and_discloses_provenance(tmp_path: Path) -> None:
    results = [
        _result(
            arm="rag",
            correct=True,
            confidence=0.8,
            unresolved=1,
            out_of_corpus=8,
            misquoted=1,
        ),
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
    assert "Fabrication rate = unresolved / (total citations - out_of_corpus)" in report
    assert "Misquote rate = misquoted / (total citations - out_of_corpus)" in report
    assert "Citation misquote rate" in report
    summary = next(line for line in report.splitlines() if line.startswith("| rag |"))
    # 1 unresolved and 1 misquoted over 6 eligible: each rate is 0.167, and
    # the old combined figure (0.333) must not appear.
    assert summary.count("0.167") >= 2
    assert "0.333" not in summary
    assert "percentile 95% confidence intervals" in report


def test_report_keeps_misquotes_out_of_fabrication_and_excludes_out_of_corpus() -> None:
    report = render_report(
        [
            _result(
                arm="rag",
                correct=True,
                confidence=0.8,
                out_of_corpus=4,
                misquoted=1,
            )
        ]
    )

    cells = [
        cell.strip()
        for cell in next(line for line in report.splitlines() if line.startswith("| rag |"))
        .strip("|")
        .split("|")
    ]
    fabrication, misquote = cells[10], cells[11]
    # 1 misquoted over 3 eligible (7 total - 4 out_of_corpus).
    assert fabrication.startswith("0.000")
    assert misquote.startswith("0.333")


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
    assert f"fewer than {MIN_CASES_FOR_INTERVALS} completed cases" in report


def test_below_the_threshold_an_arm_prints_point_values_and_no_intervals() -> None:
    """Three cases have 10 distinct bootstrap resamples; an interval over them is noise."""
    results = [
        _result(arm="full_council", correct=index != 1, confidence=0.7, case_id=f"case-{index}")
        for index in range(3)
    ]

    report = render_report(results)

    cells = _summary_cells(report, "full_council")
    accuracy, brier = cells[6], cells[7]
    assert accuracy == "0.667 (n=3)"
    assert brier.startswith("0.") and brier.endswith("(n=3)")
    point_only = re.compile(r"^(?:N/A|-?\d\.\d{3})(?: \(n=\d+\))?$")
    assert all(point_only.match(cell) for cell in cells[6:13]), cells[6:13]
    assert f"at least {MIN_CASES_FOR_INTERVALS} completed cases" in report
    assert "> **No intervals:** `full_council` (n=3)" in report


def test_at_the_threshold_intervals_come_back() -> None:
    """The bootstrap path is kept for a run large enough to use it."""
    results = [
        _result(arm="rag", correct=index % 3 != 0, confidence=0.8, case_id=f"case-{index}")
        for index in range(MIN_CASES_FOR_INTERVALS)
    ]

    report = render_report(results)

    accuracy = _summary_cells(report, "rag")[6]
    assert accuracy.startswith("0.600 (n=10) (")
    low, high = accuracy.rsplit("(", 1)[1].rstrip(")").split("-")
    assert float(low) <= 0.6 <= float(high)
    assert "No intervals" not in report


def test_the_per_case_table_puts_each_case_through_every_arm_in_ladder_order() -> None:
    results = [
        _result(arm=arm, correct=arm != "rag", confidence=0.6, case_id=case_id)
        for case_id in ("icty_galic_terror", "icc_bemba_command")
        for arm in reversed(ARM_ORDER)
    ]

    report = render_report(results)
    table = report.split("### Per case", 1)[1]
    rows = [line for line in table.splitlines() if line.startswith("| icc_bemba_command |")]

    assert [row.split("|")[3].strip() for row in rows] == list(ARM_ORDER)
    rag = _case_cells(report, "icc_bemba_command", "rag")
    assert rag[1:6] == ["affirmed", "rag", "rejected", "✗", "0.60"]
    galic = _case_cells(report, "icty_galic_terror", "full_council")
    assert galic[3:5] == ["affirmed", "✓"]


def test_the_per_case_table_shows_citation_counts_not_rates() -> None:
    report = render_report(
        [
            _result(
                arm="rag", correct=True, confidence=0.9, unresolved=1, misquoted=2, out_of_corpus=5
            )
        ]
    )

    unresolved, misquoted, eligible = _case_cells(report, "case-1", "rag")[6:9]
    # 10 total - 5 out_of_corpus = 5 eligible.
    assert (unresolved, misquoted, eligible) == ("1", "2", "5")


def test_the_per_case_table_marks_a_failed_run_instead_of_scoring_it() -> None:
    errored = _result(arm="full_council", correct=False, confidence=0.9)
    errored.update(status="error", error_type="timeout", outcome_correct=None, confidence=None)

    cells = _case_cells(render_report([errored]), "case-1", "full_council")

    assert cells[3] == "timed out"
    assert set(cells[4:]) == {"—"}


def test_independence_needs_objections_from_both_attackers() -> None:
    """Arm C has one attacker. Jaccard against nothing is 0, which read as
    'perfectly independent' from an attacker that never ran."""
    single = _result(arm="single_attacker", correct=True, confidence=0.8)
    single["objections"] = [_objection(Role.ATTACKER_DOCTRINAL, "distinction proportionality")]
    both = _result(arm="full_council", correct=True, confidence=0.8)
    both["objections"] = [
        _objection(Role.ATTACKER_DOCTRINAL, "distinction proportionality"),
        _objection(Role.ATTACKER_EVIDENTIARY, "proportionality witness"),
    ]

    report = render_report([single, both])

    assert _summary_cells(report, "single_attacker")[12] == "N/A"
    assert _case_cells(report, "case-1", "single_attacker")[9] == "—"
    # {distinction, proportionality} vs {proportionality, witness}: Jaccard 1/3.
    assert _summary_cells(report, "full_council")[12] == "0.667 (n=1)"
    assert _case_cells(report, "case-1", "full_council")[9] == "0.667"


def test_warnings_sit_after_the_summary_table_not_inside_it() -> None:
    """A line between Markdown table rows ends the table there."""
    report = render_report(
        [_result(arm=arm, correct=True, confidence=0.8) for arm in ("raw", "rag")]
    )
    lines = report.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("| Arm |"))
    table = lines[first : lines.index("", first)]

    assert all(line.startswith("|") for line in table)
    assert [row.split("|")[1].strip() for row in table[2:]] == ["raw", "rag"]


def test_arm_order_matches_the_harness_registry() -> None:
    from harness.arms import ARMS

    assert set(ARM_ORDER) == set(ARMS)


def test_the_report_names_the_index_that_scored_it() -> None:
    result = _result(arm="rag", correct=True, confidence=0.8)
    result["corpus"] = {"instruments": 23, "locators": 4000, "content_hash": "c" * 64}

    report = render_report([result])

    assert "Citation index: `cccccccccccc (23 instruments, 4000 locators)`." in report


def test_the_report_refuses_mixed_indexes_unless_told_and_then_labels_each_row() -> None:
    on_a = _result(arm="rag", correct=True, confidence=0.8, case_id="case-a")
    on_a["corpus"] = {"instruments": 9, "locators": 2218, "content_hash": "a" * 64}
    unrecorded = _result(arm="rag", correct=True, confidence=0.8, case_id="case-b")

    with pytest.raises(ValueError, match="different citation indexes"):
        render_report([on_a, unrecorded])

    report = render_report([on_a, unrecorded], allow_mixed_corpora=True)

    assert "> **Mixed citation indexes:**" in report
    assert _case_cells(report, "case-a", "rag")[-1] == "aaaaaaaaaaaa (9 instruments, 2218 locators)"
    assert _case_cells(report, "case-b", "rag")[-1] == "not recorded"


def _ruled(disposition: str, severity: str | None, *, omit_severity: bool = False) -> dict:
    objection = {
        **_objection(Role.ATTACKER_DOCTRINAL, "g"),
        "disposition": disposition,
    }
    if not omit_severity:
        objection["severity"] = severity
    return objection


def test_severity_breakdown_counts_not_stated_apart_from_minor() -> None:
    result = _result(arm="full_council", correct=True, confidence=0.7)
    result["objections"] = [
        _ruled("overruled", "fatal"),
        _ruled("overruled", "fatal"),
        _ruled("sustained", "fatal"),
        _ruled("overruled", "minor"),
        _ruled("sustained", "material"),
        _ruled("overruled", None),
        _ruled("sustained", None, omit_severity=True),
        _ruled("partial", "fatal"),
        _ruled("unaddressed", "minor"),
    ]
    counts = _severity_breakdown([result])
    assert counts["fatal"] == {"sustained": 1, "overruled": 2}
    assert counts["material"] == {"sustained": 1, "overruled": 0}
    assert counts["minor"] == {"sustained": 0, "overruled": 1}
    assert counts["not_stated"] == {"sustained": 1, "overruled": 1}


def test_the_report_shows_severity_per_arm_with_overruled_fatal_called_out() -> None:
    full = _result(arm="full_council", correct=True, confidence=0.7)
    full["objections"] = [_ruled("overruled", "fatal"), _ruled("overruled", None)]
    single = _result(arm="single_attacker", correct=True, confidence=0.7)
    report = render_report([full, single])
    assert "### Objection severity" in report
    rows = [line for line in report.splitlines() if line.startswith("| full_council | 0 / 1")]
    assert rows and rows[0].rstrip().endswith("| 1 |")
    assert "| single_attacker | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |" in report
