"""Stored results are rescored and exported without calling a model."""

from __future__ import annotations

import json
from pathlib import Path

from harness.artifacts import export, rescore, rescore_self_consistency, strip_corpus_text


def _old_arm_e() -> dict:
    # Shaped like the scored run's Bemba arm E: the judge said Yes at 0.85,
    # while 5 of 7 samples were read as "rejected", giving 0.714.
    return {
        "arm": "self_consistency",
        "predicted_outcome": "affirmed",
        "confidence": 5 / 7,
        "confidence_reasoning": "Self-consistency agreement rate (rejected: 5/7)",
        "vote_counts": {"rejected": 5, "affirmed": 1, "indeterminate": 1},
        "verdict": {"conclusion": "Yes.", "confidence": 0.85, "confidence_reasoning": "why"},
    }


def test_an_old_arm_e_result_takes_its_judges_confidence() -> None:
    result = _old_arm_e()
    assert rescore_self_consistency(result) is True
    assert result["confidence"] == 0.85
    assert result["confidence_reasoning"] == "why"
    assert result["agreement_rate"] == 5 / 7  # kept, beside the votes it came from
    assert "ADR 0011" in result["rescored"]


def test_rescoring_twice_changes_nothing_the_second_time() -> None:
    result = _old_arm_e()
    rescore_self_consistency(result)
    once = dict(result)
    assert rescore_self_consistency(result) is False
    assert result == once


def test_other_arms_are_left_alone() -> None:
    result = {"arm": "rag", "confidence": 0.7, "verdict": {"confidence": 0.9}}
    assert rescore_self_consistency(result) is False
    assert result["confidence"] == 0.7


def test_corpus_text_is_removed_at_every_depth_and_nothing_else_is() -> None:
    cited = {"citation": {"instrument": "ap_i", "article": "51(2)"}, "status": "resolved"}
    data = {
        "context": [{**cited, "corpus_text": "treaty text"}],
        "objections": [{"reasoning": "r", "resolved_citations": [{**cited, "corpus_text": "t"}]}],
    }
    assert strip_corpus_text(data) == {
        "context": [cited],
        "objections": [{"reasoning": "r", "resolved_citations": [cited]}],
    }


def test_rescore_then_export_writes_the_layout_the_report_reads(tmp_path: Path) -> None:
    results = tmp_path / "results"
    (results / "self_consistency").mkdir(parents=True)
    old = {**_old_arm_e(), "context": [{"corpus_text": "treaty text"}]}
    (results / "self_consistency" / "case_a.json").write_text(json.dumps(old))
    (results / "quota_log.json").write_text("{}")

    assert len(rescore(results)) == 1
    written = export(results, tmp_path / "out")

    assert written == [tmp_path / "out" / "self_consistency" / "case_a.json"]
    exported = json.loads(written[0].read_text())
    assert exported["confidence"] == 0.85
    assert exported["context"] == [{}]
    assert "treaty text" not in written[0].read_text()
