"""Generate a reproducible Markdown report from evaluation result artifacts."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from council_core.models.debate import Objection
from metrics.calibration import expected_calibration_error
from metrics.independence import measure_independence
from metrics.provenance import is_synthetic_result, load_result_files

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0


def _citation_counts(result: dict[str, Any]) -> tuple[int, int]:
    statuses = result.get("citation_statuses")
    if isinstance(statuses, dict):
        total = int(statuses.get("total", 0))
        out_of_corpus = int(statuses.get("out_of_corpus", 0))
        unresolved = int(statuses.get("unresolved", 0))
        return unresolved, max(0, total - out_of_corpus)

    unresolved = 0
    eligible = 0
    for collection in ("arguments", "objections"):
        for item in result.get(collection, []):
            for citation in item.get("resolved_citations", []):
                status = citation.get("status")
                if status == "out_of_corpus":
                    continue
                eligible += 1
                unresolved += status == "unresolved"
    return unresolved, eligible


def _independence(result: dict[str, Any]) -> float | None:
    objections = [Objection.model_validate(item) for item in result.get("objections", [])]
    measured = measure_independence(objections)
    if measured.doctrinal_count + measured.evidentiary_count == 0:
        return None
    return 1.0 - measured.jaccard


def _bootstrap_ci(
    values: list[float],
    metric: Any,
    *,
    seed_offset: int = 0,
) -> tuple[float, float] | None:
    if not values:
        return None
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    indices = rng.integers(0, data.size, size=(BOOTSTRAP_RESAMPLES, data.size))
    samples = np.asarray([metric(data[index]) for index in indices], dtype=float)
    return (float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5)))


def _bootstrap_paired_ci(
    confidences: list[float],
    correctness: list[bool],
    metric: Any,
    *,
    seed_offset: int,
) -> tuple[float, float] | None:
    if not confidences:
        return None
    confidence_data = np.asarray(confidences, dtype=float)
    correctness_data = np.asarray(correctness, dtype=bool)
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    indices = rng.integers(
        0,
        confidence_data.size,
        size=(BOOTSTRAP_RESAMPLES, confidence_data.size),
    )
    samples = np.asarray(
        [metric(confidence_data[index], correctness_data[index]) for index in indices],
        dtype=float,
    )
    return (float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5)))


def _bootstrap_ratio_ci(
    numerators: list[int], denominators: list[int], *, seed_offset: int
) -> tuple[float, float] | None:
    if not numerators or not any(denominators):
        return None
    numerator_data = np.asarray(numerators, dtype=float)
    denominator_data = np.asarray(denominators, dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    indices = rng.integers(
        0,
        numerator_data.size,
        size=(BOOTSTRAP_RESAMPLES, numerator_data.size),
    )
    samples = []
    for index in indices:
        denominator = denominator_data[index].sum()
        if denominator:
            samples.append(numerator_data[index].sum() / denominator)
    if not samples:
        return None
    return (float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5)))


def _format_metric(
    value: float | None,
    ci: tuple[float, float] | None,
    *,
    sample_size: int | None = None,
) -> str:
    sample_note = f" (n={sample_size})" if sample_size is not None else ""
    if value is None or not np.isfinite(value):
        return f"N/A{sample_note}"
    if ci is None or not all(np.isfinite(bound) for bound in ci):
        return f"{value:.3f}{sample_note} (95% CI N/A)"
    return f"{value:.3f}{sample_note} ({ci[0]:.3f}-{ci[1]:.3f})"


def _summarize_arm(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [result for result in results if result.get("status") != "error"]
    accuracy = [
        float(
            result.get(
                "outcome_correct",
                result.get("predicted_outcome") == result.get("ground_truth_outcome"),
            )
        )
        for result in completed
    ]
    scored = [
        result
        for result in completed
        if isinstance(result.get("confidence"), (int, float))
        and result.get("outcome_correct") is not None
    ]
    confidences = [float(result["confidence"]) for result in scored]
    correctness = [bool(result["outcome_correct"]) for result in scored]
    brier_values = [
        (confidence - float(correct)) ** 2
        for confidence, correct in zip(confidences, correctness, strict=True)
    ]

    citation_data = [_citation_counts(result) for result in results]
    unresolved = sum(count for count, _ in citation_data)
    eligible = sum(count for _, count in citation_data)
    fabrication_rate = unresolved / eligible if eligible else None
    independence_values = [
        value for result in results if (value := _independence(result)) is not None
    ]

    def average(data: np.ndarray) -> float:
        return float(np.mean(data))

    def ece(confidence_data: np.ndarray, correctness_data: np.ndarray) -> float:
        return expected_calibration_error(
            confidence_data.tolist(),
            correctness_data.tolist(),
        )

    overconfidence = float(np.mean(confidences) - np.mean(correctness)) if scored else None
    hashes_by_prompt: dict[str, set[str]] = defaultdict(set)
    for result in results:
        hashes = result.get("prompt_hashes")
        if isinstance(hashes, dict):
            for prompt, prompt_hash in hashes.items():
                hashes_by_prompt[prompt].add(str(prompt_hash))

    return {
        "n": len(results),
        "completed_n": len(completed),
        "error_n": sum(
            result.get("status") == "error" and result.get("error_type") != "timeout"
            for result in results
        ),
        "timeout_n": sum(
            result.get("status") == "error" and result.get("error_type") == "timeout"
            for result in results
        ),
        "wrong_n": sum(
            result.get(
                "outcome_correct",
                result.get("predicted_outcome") == result.get("ground_truth_outcome"),
            )
            is False
            for result in completed
        ),
        "accuracy_n": len(completed),
        "calibration_n": len(scored),
        "accuracy": float(np.mean(accuracy)) if accuracy else None,
        "accuracy_ci": _bootstrap_ci(accuracy, average, seed_offset=1),
        "brier": float(np.mean(brier_values)) if brier_values else None,
        "brier_ci": _bootstrap_ci(brier_values, average, seed_offset=2),
        "ece": expected_calibration_error(confidences, correctness) if scored else None,
        "ece_ci": _bootstrap_paired_ci(confidences, correctness, ece, seed_offset=3)
        if scored
        else None,
        "overconfidence": overconfidence,
        "overconfidence_ci": _bootstrap_paired_ci(
            confidences,
            correctness,
            lambda confidence_data, correctness_data: float(
                np.mean(confidence_data) - np.mean(correctness_data)
            ),
            seed_offset=4,
        )
        if scored
        else None,
        "fabrication_rate": fabrication_rate,
        "fabrication_ci": _bootstrap_ratio_ci(
            [count for count, _ in citation_data],
            [total for _, total in citation_data],
            seed_offset=5,
        ),
        "independence": float(np.mean(independence_values)) if independence_values else None,
        "independence_ci": _bootstrap_ci(independence_values, average, seed_offset=6),
        "judge_backends": sorted(
            {str(result.get("judge_backend", "unknown")) for result in results}
        ),
        "prompt_hashes": {
            prompt: sorted(prompt_hashes)
            for prompt, prompt_hashes in sorted(hashes_by_prompt.items())
        },
    }


def render_report(results: list[dict[str, Any]], *, allow_mixed_results: bool = False) -> str:
    """Render arm metrics while keeping synthetic and real results separate."""
    provenance = {is_synthetic_result(result) for result in results}
    if len(provenance) > 1 and not allow_mixed_results:
        raise ValueError(
            "Evaluation results contain both synthetic and real runs. "
            "Pass --allow-mixed-results to report them in separate sections."
        )
    if True in provenance and not allow_mixed_results:
        raise ValueError(
            "Synthetic results are not scored as real evaluation data. "
            "Pass --allow-mixed-results to report them in a separate section."
        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups["Synthetic (not scored)" if is_synthetic_result(result) else "Real results"].append(
            result
        )

    lines = [
        "# Evaluation report",
        "",
        f"Bootstrap: {BOOTSTRAP_RESAMPLES:,} resamples; fixed seed {BOOTSTRAP_SEED}.",
        "Intervals are percentile 95% confidence intervals.",
        "Fabrication rate = unresolved / (total citations - out_of_corpus); "
        "out_of_corpus is excluded.",
        "Independence = 1 - token-level Jaccard overlap between attacker objection grounds.",
        "",
    ]
    for group_name, group_results in groups.items():
        lines.extend((f"## {group_name}", ""))
        by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in group_results:
            by_arm[str(result.get("arm", "unknown"))].append(result)
        lines.extend(
            (
                "| Arm | Cases | Completed | Wrong | Errors | Timed out | "
                "Accuracy | Brier score | ECE | Overconfidence | "
                "Citation fabrication rate | Attacker independence | Judge backend |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
                "---: | ---: | ---: | --- |",
            )
        )
        summaries = {arm: _summarize_arm(rows) for arm, rows in sorted(by_arm.items())}
        for arm, summary in summaries.items():
            lines.append(
                f"| {arm} | {summary['n']} | {summary['completed_n']} | "
                f"{summary['wrong_n']} | {summary['error_n']} | {summary['timeout_n']} | "
                f"{_format_metric(summary['accuracy'], summary['accuracy_ci'], sample_size=summary['accuracy_n'])} | "
                f"{_format_metric(summary['brier'], summary['brier_ci'], sample_size=summary['calibration_n'])} | "
                f"{_format_metric(summary['ece'], summary['ece_ci'], sample_size=summary['calibration_n'])} | "
                f"{_format_metric(summary['overconfidence'], summary['overconfidence_ci'])} | "
                f"{_format_metric(summary['fabrication_rate'], summary['fabrication_ci'])} | "
                f"{_format_metric(summary['independence'], summary['independence_ci'])} | "
                f"{', '.join(summary['judge_backends'])} |"
            )
            if summary["completed_n"] < 5:
                lines.append(
                    f"> **Warning:** arm `{arm}` has only {summary['completed_n']} completed "
                    "cases; fewer than 5 completed cases."
                )
        lines.extend(("", "### Prompt hashes", ""))
        for arm, summary in summaries.items():
            lines.append(f"**{arm}**")
            if not summary["prompt_hashes"]:
                lines.append("- No prompt hashes recorded.")
            else:
                for prompt, hashes in summary["prompt_hashes"].items():
                    lines.append(f"- `{prompt}`: {', '.join(f'`{value}`' for value in hashes)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_report(
    *,
    results_dir: Path = Path("data/eval"),
    output_path: Path = Path("evaluation/reports/evaluation-report.md"),
    allow_mixed_results: bool = False,
) -> Path:
    """Load result artifacts from the evaluation directory and write Markdown."""
    results = load_result_files(
        results_dir,
        allow_mixed_results=allow_mixed_results,
    )
    report = render_report(results, allow_mixed_results=allow_mixed_results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Markdown evaluation report.")
    parser.add_argument("--results-dir", type=Path, default=Path("data/eval"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/reports/evaluation-report.md"),
    )
    parser.add_argument(
        "--allow-mixed-results",
        action="store_true",
        help="Report synthetic and real results in separate, clearly labelled sections.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_path = generate_report(
        results_dir=args.results_dir,
        output_path=args.output,
        allow_mixed_results=args.allow_mixed_results,
    )
    print(f"Evaluation report written to {output_path}")


if __name__ == "__main__":
    main()
