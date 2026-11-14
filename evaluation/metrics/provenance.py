"""Load evaluation results without silently mixing synthetic and real runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class MixedResultProvenanceError(ValueError):
    """Raised when a result set combines synthetic and real outputs."""


def is_synthetic_result(result: Mapping[str, Any]) -> bool:
    """Identify synthetic results, including older files without a marker."""
    if "synthetic" in result:
        synthetic = result["synthetic"]
        if not isinstance(synthetic, bool):
            raise ValueError("Result 'synthetic' field must be a boolean.")
        return synthetic

    backend = result.get("judge_backend")
    if backend == "mock":
        return True
    if backend in {"api", "local"}:
        return False
    raise ValueError("Result is missing a recognizable judge backend or synthetic marker.")


def validate_result_provenance(
    results: list[Mapping[str, Any]], *, allow_mixed_results: bool = False
) -> None:
    """Reject result sets containing both synthetic and real records by default."""
    provenance = {is_synthetic_result(result) for result in results}
    if len(provenance) > 1 and not allow_mixed_results:
        raise MixedResultProvenanceError(
            "Evaluation results contain both synthetic and real runs. "
            "Pass --allow-mixed-results to proceed explicitly."
        )


def load_result_files(
    results_dir: Path, *, allow_mixed_results: bool = False
) -> list[dict[str, Any]]:
    """Load per-arm result JSON files and enforce provenance consistency."""
    results: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*/*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError(f"Evaluation result must be a JSON object: {path}")
        results.append(result)

    validate_result_provenance(results, allow_mixed_results=allow_mixed_results)
    return results
