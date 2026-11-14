"""Load evaluation results without silently mixing synthetic and real runs,
or results scored against different citation indexes."""

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


class MixedCorpusError(ValueError):
    """Raised when a result set was scored against more than one citation index."""


def corpus_label(result: Mapping[str, Any]) -> str:
    """A short, stable name for the index that scored a result.

    "not recorded" for a result written before results carried one. That is
    its own group, not a wildcard: nothing says which index it matches.
    """
    corpus = result.get("corpus")
    if not isinstance(corpus, Mapping) or not corpus.get("content_hash"):
        return "not recorded"
    return (
        f"{str(corpus['content_hash'])[:12]} "
        f"({corpus.get('instruments', '?')} instruments, {corpus.get('locators', '?')} locators)"
    )


def validate_corpus_consistency(
    results: list[Mapping[str, Any]], *, allow_mixed_corpora: bool = False
) -> None:
    """Reject results scored against different indexes, by default.

    A fabrication rate is a statement about one index. Pooled across two, it
    describes neither: the same citation can be `resolved` on one machine and
    `out_of_corpus` on another.
    """
    labels = sorted({corpus_label(result) for result in results})
    if len(labels) > 1 and not allow_mixed_corpora:
        raise MixedCorpusError(
            "Evaluation results were scored against different citation indexes: "
            + "; ".join(labels)
            + ". Re-run against one index, or pass --allow-mixed-corpora to report them anyway."
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
