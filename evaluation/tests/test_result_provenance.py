"""Tests for synthetic versus real evaluation result handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.provenance import (
    MixedCorpusError,
    MixedResultProvenanceError,
    corpus_label,
    load_result_files,
    validate_corpus_consistency,
    validate_result_provenance,
)


def test_report_result_loader_rejects_mixed_provenance_by_default(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    rag_dir = tmp_path / "rag"
    raw_dir.mkdir()
    rag_dir.mkdir()
    (raw_dir / "synthetic.json").write_text(
        json.dumps({"judge_backend": "mock", "synthetic": True}), encoding="utf-8"
    )
    (rag_dir / "real.json").write_text(
        json.dumps({"judge_backend": "api", "synthetic": False}), encoding="utf-8"
    )

    with pytest.raises(MixedResultProvenanceError, match="both synthetic and real"):
        load_result_files(tmp_path)

    results = load_result_files(tmp_path, allow_mixed_results=True)
    assert len(results) == 2


def test_provenance_infers_synthetic_from_legacy_backend() -> None:
    validate_result_provenance([{"judge_backend": "mock"}])
    with pytest.raises(MixedResultProvenanceError):
        validate_result_provenance([{"judge_backend": "mock"}, {"judge_backend": "api"}])


def _scored_on(content_hash: str | None) -> dict:
    result: dict = {"judge_backend": "api", "synthetic": False}
    if content_hash is not None:
        result["corpus"] = {"instruments": 9, "locators": 2218, "content_hash": content_hash}
    return result


def test_results_from_one_index_pass() -> None:
    validate_corpus_consistency([_scored_on("a" * 64), _scored_on("a" * 64)])


def test_results_from_two_indexes_are_refused_by_default() -> None:
    """The same citation can be resolved on one machine and out_of_corpus on another."""
    results = [_scored_on("a" * 64), _scored_on("b" * 64)]

    with pytest.raises(MixedCorpusError, match="different citation indexes"):
        validate_corpus_consistency(results)

    validate_corpus_consistency(results, allow_mixed_corpora=True)


def test_a_result_with_no_recorded_index_is_its_own_group() -> None:
    """Not recorded is not a wildcard: nothing says which index it matches."""
    with pytest.raises(MixedCorpusError, match="not recorded"):
        validate_corpus_consistency([_scored_on("a" * 64), _scored_on(None)])

    validate_corpus_consistency([_scored_on(None), _scored_on(None)])


def test_the_label_names_the_index_briefly() -> None:
    assert corpus_label(_scored_on("0123456789abcdef" * 4)) == (
        "0123456789ab (9 instruments, 2218 locators)"
    )
    assert corpus_label(_scored_on(None)) == "not recorded"
