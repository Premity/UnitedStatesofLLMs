"""Tests for synthetic versus real evaluation result handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.provenance import (
    MixedResultProvenanceError,
    load_result_files,
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
