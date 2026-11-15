"""Tests for hand-scored reasoning overlap (GitHub #27)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from metrics.reasoning_overlap import (
    DEFAULT_SCORES_PATH,
    RUBRIC_VERSION,
    OverlapScore,
    agreement,
    key_reasoning_counts,
    load_scores,
    match_to_results,
    run_overlap,
    validate_scores,
)

COUNTS = {"case-1": 4}


def _score(
    points: list[int], *, run_id: str = "run-a", scorer: str = "s1", arm: str = "full_council"
) -> OverlapScore:
    return OverlapScore(case_id="case-1", arm=arm, run_id=run_id, scorer=scorer, points=points)


def _result(arm: str, run_id: str, *, status: str = "completed") -> dict:
    return {
        "case_id": "case-1",
        "arm": arm,
        "run_id": run_id,
        "status": status,
        "judge_backend": "api",
        "synthetic": False,
        "ground_truth_outcome": "affirmed",
        "predicted_outcome": "affirmed",
        "outcome_correct": True,
        "confidence": 0.8,
        "objections": [],
        "citation_statuses": {"total": 0},
        "prompt_hashes": {},
    }


def test_a_run_scores_its_share_of_the_available_points() -> None:
    assert _score([2, 2, 2, 2]).score == 1.0
    assert _score([0, 0, 0, 0]).score == 0.0
    assert _score([2, 1, 0, 1]).score == pytest.approx(0.5)


def test_a_point_outside_the_scale_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _score([3, 0, 0, 0])
    with pytest.raises(ValidationError):
        _score([-1, 0, 0, 0])


def test_one_point_per_key_reasoning_entry() -> None:
    with pytest.raises(ValueError, match="3 points, but case-1 has 4"):
        validate_scores([_score([2, 1, 0])], COUNTS)


def test_an_unknown_case_is_rejected() -> None:
    score = OverlapScore(case_id="nope", arm="raw", run_id="r", scorer="s1", points=[1])
    with pytest.raises(ValueError, match="unknown case"):
        validate_scores([score], COUNTS)


def test_a_scorer_scores_a_run_once() -> None:
    with pytest.raises(ValueError, match="scored twice"):
        validate_scores([_score([2, 2, 2, 2]), _score([0, 0, 0, 0])], COUNTS)


def test_two_scorers_average_and_their_agreement_is_counted() -> None:
    scores = [_score([2, 1, 0, 2], scorer="s1"), _score([2, 2, 0, 1], scorer="s2")]

    assert run_overlap(scores) == pytest.approx((5 / 8 + 5 / 8) / 2)
    assert agreement(scores) == (2, 4)


def test_one_scorer_gives_no_agreement_figure() -> None:
    assert agreement([_score([2, 1, 0, 2])]) == (0, 0)


def test_scores_file_under_another_rubric_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "scores.json"
    path.write_text(json.dumps({"rubric_version": RUBRIC_VERSION + 1, "scores": []}))

    with pytest.raises(ValueError, match="rubric version"):
        load_scores(path)


def test_a_missing_scores_file_means_nothing_is_scored(tmp_path: Path) -> None:
    assert load_scores(tmp_path / "absent.json") == []


def test_the_committed_scores_file_is_valid_against_the_real_cases() -> None:
    """The file in the repo must always load: the report reads it by default."""
    load_scores(DEFAULT_SCORES_PATH)
    counts = key_reasoning_counts()
    assert counts, "no case files found"
    assert all(n > 0 for n in counts.values())


def test_a_score_naming_the_wrong_arm_for_its_run_is_an_error() -> None:
    with pytest.raises(ValueError, match="that run is case-1/raw"):
        match_to_results([_score([2, 2, 2, 2], run_id="run-a")], [_result("raw", "run-a")])
