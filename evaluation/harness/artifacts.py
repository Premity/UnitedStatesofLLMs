"""Prepare stored results for the report and for the repo.

Two steps, both on results already written, neither calling a model:

- `rescore`: give an arm E result written before ADR 0011's amendment its
  judge's confidence, in place. Such a result carries the samples' agreement
  rate as its confidence, read from the presenter's wording; see ADR 0011.
- `export`: copy results into the repo without the corpus text. The repo is
  public and nobody has checked the redistribution terms of the treaty texts
  (ADR 0014), so every `corpus_text` field is dropped. What a reader needs to
  check a dissent log stays: arguments, objections, rulings and their reasons,
  citation locators, statuses and source URLs.

    python -m harness.artifacts rescore --results-dir data/eval-combined
    python -m harness.artifacts export --results-dir data/eval-combined \\
        --output-dir evaluation/results/scored-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SELF_CONSISTENCY = "self_consistency"


def rescore_self_consistency(result: dict[str, Any]) -> bool:
    """Move an old arm E result's confidence to its judge's. True if it changed.

    The agreement rate it carried is kept, as `agreement_rate`, next to the
    vote counts it came from. A result already carrying `agreement_rate` was
    written by the amended harness and is left alone, as is any other arm.
    """
    if result.get("arm") != SELF_CONSISTENCY or "agreement_rate" in result:
        return False
    verdict = result.get("verdict") or {}
    result["agreement_rate"] = result.get("confidence")
    result["confidence"] = verdict.get("confidence")
    result["confidence_reasoning"] = verdict.get("confidence_reasoning", "")
    result["rescored"] = (
        "Confidence moved from the samples' agreement rate to the judge's stated "
        "confidence after the run (ADR 0011, amended). No model was called."
    )
    return True


def strip_corpus_text(value: Any) -> Any:
    """The value with every `corpus_text` field removed, at any depth."""
    if isinstance(value, dict):
        return {k: strip_corpus_text(v) for k, v in value.items() if k != "corpus_text"}
    if isinstance(value, list):
        return [strip_corpus_text(v) for v in value]
    return value


def _result_files(results_dir: Path) -> list[Path]:
    return sorted(p for p in results_dir.glob("*/*.json") if p.name != "quota_log.json")


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rescore(results_dir: Path) -> list[Path]:
    """Rescore every old arm E result under `results_dir` in place."""
    changed = []
    for path in _result_files(results_dir):
        data = json.loads(path.read_text(encoding="utf-8"))
        if rescore_self_consistency(data):
            _write(path, data)
            changed.append(path)
    return changed


def export(results_dir: Path, output_dir: Path) -> list[Path]:
    """Copy every result to `output_dir/<arm>/<case>.json` without corpus text."""
    written = []
    for path in _result_files(results_dir):
        data = json.loads(path.read_text(encoding="utf-8"))
        target = output_dir / path.parent.name / path.name
        _write(target, strip_corpus_text(data))
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rescore_p = sub.add_parser("rescore", help="Give old arm E results the judge's confidence.")
    rescore_p.add_argument("--results-dir", type=Path, required=True)
    export_p = sub.add_parser("export", help="Copy results without corpus text.")
    export_p.add_argument("--results-dir", type=Path, required=True)
    export_p.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "rescore":
        changed = rescore(args.results_dir)
        print(f"Rescored {len(changed)} arm E result(s).")
        for path in changed:
            print(f"  {path}")
    else:
        written = export(args.results_dir, args.output_dir)
        print(f"Exported {len(written)} result(s) to {args.output_dir}, corpus text removed.")


if __name__ == "__main__":
    main()
