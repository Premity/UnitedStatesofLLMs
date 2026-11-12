"""Evaluation harness runner (T4-1).

Drives the ablation arms over the case fixtures, measures outcomes, and writes
structured results to `data/eval/`.

Usage:
    make eval-arm ARM=rag
    make eval-arm ARM=full_council
    python -m harness.run --arm rag --dry-run
    python -m harness.run --all-arms --dry-run --limit 1
    python -m harness.run --arm rag --resume
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

import council_core.llm.client as llm_client

# Ensure local LiteLLM model cost map is used to prevent network timeouts in sandbox
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# If running on host rather than inside Docker, resolve host-relative paths
if "PROMPTS_DIR" not in os.environ and not Path("/app/prompts").exists():
    host_prompts = (Path.cwd() / "prompts").resolve()
    if host_prompts.exists():
        os.environ["PROMPTS_DIR"] = str(host_prompts)

if "DATA_DIR" not in os.environ and not Path("/data").exists():
    host_data = (Path.cwd() / "data").resolve()
    if host_data.exists():
        os.environ["DATA_DIR"] = str(host_data)

from app.core.config import get_role_models, get_settings
from app.graph.workflow import compiled_graph
from app.roles.judge import JudgeRole
from app.roles.presenter import PresenterRole
from app.services.retrieval import get_retrieval_service
from council_core.llm import CouncilLLM
from council_core.models.citation import CitationStatus, ResolvedCitation
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    ObjectionDisposition,
    Role,
    Turn,
    Verdict,
)
from harness.arms import ARMS, Arm, SelfConsistencyArm
from harness.cases import EvaluationCase, Outcome, load_cases
from harness.quota import (
    MAX_DAILY_QUOTA,
    QuotaExceededError,
    QuotaTracker,
    get_expected_calls,
)
from harness.sampling import (
    PresenterSample,
    aggregate_samples,
    derive_sample_count,
)
from metrics.provenance import (
    is_synthetic_result,
    load_result_files,
    validate_result_provenance,
)

log = structlog.get_logger(__name__)

DEFAULT_CASE_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_CONSECUTIVE_FAILURES = 2


class _JudgeRequestCounter:
    """Counts judge HTTP attempts from the LLM client's structured log events."""

    def __init__(self) -> None:
        self.attempts = 0
        self.responses = 0
        self.structured_failures = 0

    @property
    def failures(self) -> int:
        """Return failed HTTP attempts plus terminal structured-output failures."""
        return max(0, self.attempts - self.responses) + self.structured_failures


class _CountingLLMLogger:
    """Intercept judge request events while forwarding normal LLM logging."""

    def __init__(self, wrapped: Any, counter: _JudgeRequestCounter) -> None:
        self._wrapped = wrapped
        self._counter = counter

    def info(self, event: str, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("role") == "judge":
            if event == "llm_request":
                self._counter.attempts += 1
            elif event == "llm_response":
                self._counter.responses += 1
        return self._wrapped.info(event, *args, **kwargs)

    def error(self, event: str, *args: Any, **kwargs: Any) -> Any:
        if event == "structured_output_failed" and kwargs.get("role") == "judge":
            self._counter.structured_failures += 1
        return self._wrapped.error(event, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


@contextmanager
def _capture_judge_requests() -> Iterator[_JudgeRequestCounter]:
    """Capture each judge request event for one sequential harness case."""
    counter = _JudgeRequestCounter()
    original_logger = llm_client.log
    llm_client.log = _CountingLLMLogger(original_logger, counter)
    try:
        yield counter
    finally:
        llm_client.log = original_logger


ARM_ALIASES: dict[str, str] = {
    "a": "raw",
    "raw": "raw",
    "b": "rag",
    "rag": "rag",
    "c": "single_attacker",
    "single_attacker": "single_attacker",
    "d": "full_council",
    "full_council": "full_council",
    "e": "self_consistency",
    "self_consistency": "self_consistency",
}


def normalize_outcome(conclusion: str | None) -> str:
    """Normalize a free-text conclusion or holding into a standard Outcome value."""
    if not conclusion:
        return Outcome.INDETERMINATE.value
    text = conclusion.lower().strip()
    answer = re.match(r"^(yes|no)\b", text)
    if answer:
        return Outcome.AFFIRMED.value if answer.group(1) == "yes" else Outcome.REJECTED.value
    if text in ("affirmed", "affirm", "yes", "violation"):
        return Outcome.AFFIRMED.value
    if text in ("rejected", "reject", "no", "no violation", "dismissed"):
        return Outcome.REJECTED.value
    if text in ("indeterminate", "uncertain", "unresolved"):
        return Outcome.INDETERMINATE.value

    # Search for explicit patterns in legal prose
    if any(
        kw in text
        for kw in (
            "not criminally responsible",
            "not criminally liable",
            "cannot be held criminally responsible",
            "cannot be held criminally liable",
            "no criminal responsibility",
            "does not bear criminal responsibility",
            "has not been established",
            "does not constitute",
            "did not constitute",
            "is not a violation",
            "no violation",
            "rejected",
            "dismissed",
            "fails to establish",
        )
    ):
        return Outcome.REJECTED.value
    if any(
        kw in text
        for kw in (
            "constitutes a violation",
            "constitutes",
            "is a violation",
            "bears criminal responsibility",
            "criminally responsible",
            "criminally liable",
            "prohibited",
            "affirmed",
            "convicted",
            "war crime",
            "breach",
        )
    ):
        return Outcome.AFFIRMED.value

    return Outcome.INDETERMINATE.value


def extract_sample_outcome(arguments: list[Argument], question: str) -> str:
    """Extract candidate outcome from presenter arguments for self-consistency voting."""
    combined = " ".join(f"{a.claim} {a.reasoning}" for a in arguments).lower()
    if any(
        kw in combined
        for kw in (
            "does not constitute",
            "did not constitute",
            "is not a violation",
            "no violation",
            "lawful",
            "rejected",
        )
    ):
        return Outcome.REJECTED.value
    if any(
        kw in combined
        for kw in (
            "constitutes",
            "is a violation",
            "prohibited",
            "breach",
            "unlawful",
            "war crime",
            "affirmed",
        )
    ):
        return Outcome.AFFIRMED.value
    return Outcome.AFFIRMED.value


def compute_prompt_hashes(prompts_dir: Path | None = None) -> dict[str, str]:
    """Compute SHA-256 hashes of all markdown prompt templates in prompts_dir."""
    pdir = prompts_dir or get_settings().prompts_dir
    hashes: dict[str, str] = {}
    if not pdir.exists():
        return hashes
    for path in sorted(pdir.rglob("*.md")):
        rel = path.relative_to(pdir).as_posix()
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def composite_prompt_hash(hashes: dict[str, str]) -> str:
    """Compute single composite hash across all template hashes."""
    canonical = "\n".join(f"{k}:{v}" for k, v in sorted(hashes.items()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MockJudgeRole:
    """Mock judge for dry-runs and tests without network calls or API quota usage."""

    role = Role.JUDGE

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def run(
        self,
        *,
        config: DebateConfig,
        context: list[ResolvedCitation],
        arguments: list[Argument],
        objections: list[Objection],
        round_number: int,
    ) -> tuple[Turn, Verdict, bool]:
        dissent: list[Objection] = []
        for obj in objections:
            obj.disposition = ObjectionDisposition.OVERRULED
            obj.disposition_reasoning = f"Mock ruling overruling objection {obj.id}."
            dissent.append(obj)

        verdict = Verdict(
            conclusion="affirmed",
            reasoning="Mock judge conclusion affirming the question based on arguments.",
            confidence=0.85,
            confidence_reasoning="Mock confidence assessment for evaluation dry run.",
            surviving_argument_ids=[a.id for a in arguments],
            dissent=dissent,
        )
        turn = Turn(
            role=Role.JUDGE,
            round_number=round_number,
            model_id="mock_judge",
            arguments=[],
            objections=[],
            prompt_id="judge/rule",
            prompt_hash="mock_prompt_hash",
        )
        return turn, verdict, False  # novel_objections_raised=False closes auto debate


async def _run_standard_arm(
    arm: Arm,
    case: EvaluationCase,
    *,
    judge_backend: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Execute one standard debate arm (A, B, C, or D) over a case fixture."""
    config = DebateConfig(
        question=case.question,
        facts=case.facts,
        retrieval_enabled=arm.retrieval_enabled,
        enabled_attackers=list(arm.attackers),
        max_rounds=arm.max_rounds,
        rounds="auto",
    )

    run_id = f"eval_{uuid4().hex[:10]}"
    initial_state = {
        "run_id": run_id,
        "config": config,
        "current_round": 0,
        "excluded_case_id": case.source_case_id,
    }

    started = datetime.now(UTC)

    if judge_backend == "mock":
        # Fully synthetic path: zero LLM/network calls.
        mock_arg = Argument(claim="Mock claim (dry-run).", reasoning="Mock reasoning.")
        mock_verdict = Verdict(
            conclusion="affirmed",
            reasoning="Mock judge conclusion (dry-run).",
            confidence=0.85,
            confidence_reasoning="Mock confidence (dry-run).",
            surviving_argument_ids=[mock_arg.id],
            dissent=[],
        )
        presenter_turn = Turn(
            role=Role.PRESENTER,
            round_number=1,
            model_id="mock_presenter",
            arguments=[mock_arg],
            prompt_id="presenter/argue",
            prompt_hash="mock_presenter_hash",
        )
        judge_turn = Turn(
            role=Role.JUDGE,
            round_number=1,
            model_id="mock_judge",
            arguments=[],
            prompt_id="judge/rule",
            prompt_hash="mock_judge_hash",
        )
        final_state = {
            "run_id": run_id,
            "config": config,
            "current_round": 1,
            "turns": [presenter_turn, judge_turn],
            "arguments": [mock_arg],
            "objections": [],
            "context": [],
            "verdict": mock_verdict,
        }
    else:
        final_state = await compiled_graph.ainvoke(initial_state)

    duration = (datetime.now(UTC) - started).total_seconds()

    if judge_backend == "mock":
        turns: list[Turn] = final_state.get("turns", [])
        arguments: list[Argument] = final_state.get("arguments", [])
        objections: list[Objection] = final_state.get("objections", [])
        context: list[ResolvedCitation] = final_state.get("context", [])
        verdict: Verdict | None = final_state.get("verdict")
        actual_judge_calls = 0
    else:
        turns = final_state.get("turns", [])
        arguments = final_state.get("arguments", [])
        objections = final_state.get("objections", [])
        context = final_state.get("context", [])
        verdict = final_state.get("verdict")
        actual_judge_calls = sum(1 for turn in turns if turn.role == Role.JUDGE)

    predicted_outcome = (
        normalize_outcome(verdict.conclusion) if verdict else Outcome.INDETERMINATE.value
    )
    outcome_correct = predicted_outcome == case.outcome.value
    confidence = verdict.confidence if verdict else None
    confidence_reasoning = verdict.confidence_reasoning if verdict else ""

    all_resolved = [rc for a in arguments for rc in a.resolved_citations] + [
        rc for o in objections for rc in o.resolved_citations
    ]
    citation_statuses = {
        "total": len(all_resolved),
        "resolved": sum(1 for rc in all_resolved if rc.status == CitationStatus.RESOLVED),
        "unresolved": sum(1 for rc in all_resolved if rc.status == CitationStatus.UNRESOLVED),
        "out_of_corpus": sum(1 for rc in all_resolved if rc.status == CitationStatus.OUT_OF_CORPUS),
        "misquoted": sum(1 for rc in all_resolved if rc.status == CitationStatus.MISQUOTED),
    }

    return {
        "case_id": case.id,
        "case_title": case.title,
        "court": case.court,
        "year": case.year,
        "difficulty": case.difficulty,
        "arm": arm.key,
        "arm_label": arm.label,
        "run_id": run_id,
        "question": case.question,
        "facts": case.facts,
        "ground_truth_outcome": case.outcome.value,
        "holding": case.holding,
        "predicted_outcome": predicted_outcome,
        "outcome_correct": outcome_correct,
        "confidence": confidence,
        "confidence_reasoning": confidence_reasoning,
        "rounds": final_state.get("current_round", 1),
        "judge_backend": judge_backend,
        "synthetic": judge_backend == "mock",
        "judge_calls": actual_judge_calls,
        "total_calls": len(turns),
        "citation_statuses": citation_statuses,
        "verdict": verdict.model_dump(mode="json") if verdict else None,
        "dissent": [d.model_dump(mode="json") for d in (verdict.dissent if verdict else [])],
        "arguments": [a.model_dump(mode="json") for a in arguments],
        "objections": [o.model_dump(mode="json") for o in objections],
        "context": [c.model_dump(mode="json") for c in context],
        "turns": [t.model_dump(mode="json") for t in turns],
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_seconds": duration,
        "error": None,
    }


async def _run_arm_e(
    arm: SelfConsistencyArm,
    case: EvaluationCase,
    *,
    judge_backend: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Execute Arm E: Compute-matched self-consistency control over a case fixture (ADR 0011)."""
    started = datetime.now(UTC)
    run_id = f"eval_{uuid4().hex[:10]}"

    # Retrieve context once if retrieval is enabled (skip entirely in mock mode)
    context: list[ResolvedCitation] = []
    if arm.retrieval_enabled and judge_backend != "mock":
        service = get_retrieval_service()
        query = f"{case.question}\n\n{case.facts}".strip()
        context = await service.search(
            query,
            top_k=8,
            excluded_case_id=case.source_case_id,
        )

    # Derive sample count n from Arm D's call count on the same case
    arm_d_file = output_dir / "full_council" / f"{case.id}.json"
    if arm_d_file.exists():
        try:
            d_data = json.loads(arm_d_file.read_text(encoding="utf-8"))
            d_calls = int(d_data.get("total_calls", len(d_data.get("turns", []))))
        except Exception:
            d_calls = 4
    else:
        # Default to 1-round baseline (4 calls) if Arm D has not run yet
        d_calls = 4

    n_samples = derive_sample_count(d_calls, has_judge=True)

    config = DebateConfig(
        question=case.question,
        facts=case.facts,
        retrieval_enabled=arm.retrieval_enabled,
        enabled_attackers=[],
        max_rounds=1,
    )

    models = get_role_models()
    presenter_model_cfg = models.for_role(Role.PRESENTER.value).model_copy(
        update={"temperature": arm.temperature}
    )

    samples: list[PresenterSample] = []
    presenter_turns: list[Turn] = []

    for i in range(n_samples):
        presenter = PresenterRole()
        presenter._llm = CouncilLLM(presenter_model_cfg, role=Role.PRESENTER.value)
        turn = await presenter.run(
            config=config,
            context=context,
            prior_arguments=[],
            prior_objections=[],
            round_number=1,
        )
        presenter_turns.append(turn)
        sample_outcome = extract_sample_outcome(turn.arguments, case.question)
        samples.append(
            PresenterSample(
                sample_id=f"sample_{i + 1}",
                arguments=turn.arguments,
                outcome=sample_outcome,
                confidence=0.8,
            )
        )

    # Aggregate samples via majority voting
    agg = aggregate_samples(samples)

    # Pass winning aggregate arguments to the judge once
    judge_role = MockJudgeRole() if judge_backend == "mock" else JudgeRole()
    judge_turn, verdict, _ = await judge_role.run(
        config=config,
        context=context,
        arguments=agg.aggregated_arguments,
        objections=[],
        round_number=1,
    )

    duration = (datetime.now(UTC) - started).total_seconds()
    actual_judge_calls = 1 if judge_backend != "mock" else 0

    predicted_outcome = normalize_outcome(agg.winning_outcome)
    outcome_correct = predicted_outcome == case.outcome.value
    confidence = agg.agreement_rate
    confidence_reasoning = (
        f"Self-consistency agreement rate ({agg.winning_outcome}: "
        f"{agg.vote_counts.get(agg.winning_outcome or '', 0)}/{agg.total_samples})"
    )

    all_resolved = [rc for a in agg.aggregated_arguments for rc in a.resolved_citations]
    citation_statuses = {
        "total": len(all_resolved),
        "resolved": sum(1 for rc in all_resolved if rc.status == CitationStatus.RESOLVED),
        "unresolved": sum(1 for rc in all_resolved if rc.status == CitationStatus.UNRESOLVED),
        "out_of_corpus": sum(1 for rc in all_resolved if rc.status == CitationStatus.OUT_OF_CORPUS),
        "misquoted": sum(1 for rc in all_resolved if rc.status == CitationStatus.MISQUOTED),
    }

    all_turns = [*presenter_turns, judge_turn]

    return {
        "case_id": case.id,
        "case_title": case.title,
        "court": case.court,
        "year": case.year,
        "difficulty": case.difficulty,
        "arm": arm.key,
        "arm_label": arm.label,
        "run_id": run_id,
        "question": case.question,
        "facts": case.facts,
        "ground_truth_outcome": case.outcome.value,
        "holding": case.holding,
        "predicted_outcome": predicted_outcome,
        "outcome_correct": outcome_correct,
        "confidence": confidence,
        "confidence_reasoning": confidence_reasoning,
        "rounds": 1,
        "judge_backend": judge_backend,
        "synthetic": judge_backend == "mock",
        "judge_calls": actual_judge_calls,
        "total_calls": len(all_turns),
        "samples": n_samples,
        "vote_counts": agg.vote_counts,
        "citation_statuses": citation_statuses,
        "verdict": verdict.model_dump(mode="json") if verdict else None,
        "dissent": [d.model_dump(mode="json") for d in (verdict.dissent if verdict else [])],
        "arguments": [a.model_dump(mode="json") for a in agg.aggregated_arguments],
        "objections": [],
        "context": [c.model_dump(mode="json") for c in context],
        "turns": [t.model_dump(mode="json") for t in all_turns],
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_seconds": duration,
        "error": None,
    }


async def run_case(
    arm: Arm,
    case: EvaluationCase,
    *,
    judge_backend: str,
    output_dir: Path,
    quota_tracker: QuotaTracker,
    case_timeout: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run an arm over one case fixture and return the result payload."""
    started = time.perf_counter()
    prompt_hashes: dict[str, str] = {}
    model_roster: dict[str, str] = {}

    with _capture_judge_requests() as request_counter:
        timeout_scope = asyncio.timeout(case_timeout)
        try:
            async with timeout_scope:
                prompt_hashes = compute_prompt_hashes()
                models = get_role_models()
                model_roster = {
                    role: models.for_role(role).model_id
                    for role in (
                        "presenter",
                        "attacker_doctrinal",
                        "attacker_evidentiary",
                        "judge",
                    )
                }

                if isinstance(arm, SelfConsistencyArm):
                    result = await _run_arm_e(
                        arm,
                        case,
                        judge_backend=judge_backend,
                        output_dir=output_dir,
                    )
                else:
                    result = await _run_standard_arm(
                        arm,
                        case,
                        judge_backend=judge_backend,
                        output_dir=output_dir,
                    )
            result["status"] = "completed"
        except TimeoutError as exc:
            timed_out = timeout_scope.expired()
            message = (
                f"Case timed out after {case_timeout:g} seconds"
                if timed_out
                else str(exc) or "Judge request timed out"
            )
            log.exception("eval_case_failed", arm=arm.key, case_id=case.id)
            result = {
                "case_id": case.id,
                "case_title": case.title,
                "court": case.court,
                "year": case.year,
                "difficulty": case.difficulty,
                "arm": arm.key,
                "arm_label": arm.label,
                "run_id": f"eval_err_{uuid4().hex[:8]}",
                "question": case.question,
                "facts": case.facts,
                "ground_truth_outcome": case.outcome.value,
                "holding": case.holding,
                "predicted_outcome": None,
                "outcome_correct": None,
                "confidence": None,
                "confidence_reasoning": "",
                "rounds": 0,
                "judge_backend": judge_backend,
                "judge_calls": 0,
                "total_calls": 0,
                "verdict": None,
                "dissent": [],
                "arguments": [],
                "objections": [],
                "context": [],
                "turns": [],
                "timestamp": datetime.now(UTC).isoformat(),
                "duration_seconds": 0.0,
                "status": "error",
                "error_type": "timeout" if timed_out else "error",
                "error": message,
            }
        except Exception as exc:
            log.exception("eval_case_failed", arm=arm.key, case_id=case.id)
            result = {
                "case_id": case.id,
                "case_title": case.title,
                "court": case.court,
                "year": case.year,
                "difficulty": case.difficulty,
                "arm": arm.key,
                "arm_label": arm.label,
                "run_id": f"eval_err_{uuid4().hex[:8]}",
                "question": case.question,
                "facts": case.facts,
                "ground_truth_outcome": case.outcome.value,
                "holding": case.holding,
                "predicted_outcome": None,
                "outcome_correct": None,
                "confidence": None,
                "confidence_reasoning": "",
                "rounds": 0,
                "judge_backend": judge_backend,
                "judge_calls": 0,
                "total_calls": 0,
                "verdict": None,
                "dissent": [],
                "arguments": [],
                "objections": [],
                "context": [],
                "turns": [],
                "timestamp": datetime.now(UTC).isoformat(),
                "duration_seconds": 0.0,
                "status": "error",
                "error_type": "error",
                "error": str(exc),
            }
        finally:
            attempts = request_counter.attempts
            quota_tracker.record_call(
                case_id=case.id,
                arm_key=arm.key,
                calls=attempts if judge_backend == "api" else 0,
                attempts=attempts,
                failures=request_counter.failures,
                backend=judge_backend,
            )

    result["prompt_hashes"] = prompt_hashes
    result["composite_prompt_hash"] = composite_prompt_hash(prompt_hashes)
    result["model_roster"] = model_roster
    result["synthetic"] = judge_backend == "mock"
    result["judge_attempts"] = request_counter.attempts
    result["judge_failures"] = request_counter.failures
    result["judge_failed"] = result["status"] == "error" and request_counter.failures > 0
    result["duration_seconds"] = time.perf_counter() - started
    return result


def resolve_arm(arm_identifier: str) -> Arm:
    """Resolve an arm by name or letter code (A-E, raw, rag, etc.)."""
    cleaned = arm_identifier.strip().lower()
    canonical = ARM_ALIASES.get(cleaned)
    if canonical is None or canonical not in ARMS:
        valid = ", ".join(f"{k} ({v.label})" for k, v in ARMS.items())
        raise ValueError(f"Unknown arm '{arm_identifier}'. Valid arms: {valid}")
    return ARMS[canonical]


async def run_evaluation(
    *,
    arms: list[Arm],
    cases: list[EvaluationCase],
    judge_backend: str,
    output_dir: Path,
    quota_tracker: QuotaTracker,
    resume: bool = False,
    auto_go: bool = False,
    allow_mixed_results: bool = False,
    case_timeout: float = DEFAULT_CASE_TIMEOUT_SECONDS,
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES,
) -> list[dict[str, Any]]:
    """Drive one or more arms across case fixtures, handling quota and persistence."""
    if case_timeout <= 0:
        raise ValueError("case_timeout must be greater than zero")
    if max_consecutive_failures <= 0:
        raise ValueError("max_consecutive_failures must be greater than zero")

    run_started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_results: list[dict[str, Any]] = []

    existing_results = load_result_files(output_dir, allow_mixed_results=allow_mixed_results)
    validate_result_provenance(
        [*existing_results, {"synthetic": judge_backend == "mock"}],
        allow_mixed_results=allow_mixed_results,
    )

    # Calculate pending cases taking resume into account
    pending_tasks: list[tuple[Arm, EvaluationCase]] = []
    for arm in arms:
        arm_dir = output_dir / arm.key
        arm_dir.mkdir(parents=True, exist_ok=True)
        for case in cases:
            case_file = arm_dir / f"{case.id}.json"
            if resume and case_file.exists():
                try:
                    loaded = json.loads(case_file.read_text(encoding="utf-8"))
                    if loaded.get("status") == "error":
                        pending_tasks.append((arm, case))
                        continue
                    loaded["synthetic"] = is_synthetic_result(loaded)
                    case_file.write_text(json.dumps(loaded, indent=2), encoding="utf-8")
                    log.info("case_resumed_from_disk", arm=arm.key, case_id=case.id)
                    all_results.append(loaded)
                    continue
                except Exception:
                    pass
            pending_tasks.append((arm, case))

    if not pending_tasks:
        print("All case/arm pairs already completed on disk (--resume). Nothing to run.")
        _print_run_summary(run_started, quota_tracker)
        return all_results

    # Quota verification for live runs
    if judge_backend == "api":
        expected_calls = sum(get_expected_calls(arm.key, 1) for arm, _ in pending_tasks)
        reserved_attempts = expected_calls * 3
        today_usage = quota_tracker.get_today_usage()

        print("\n--- Live API Judge Run ---")
        print(f"Scheduled cases: {len(pending_tasks)}")
        print(f"Expected judge calls: {expected_calls}")
        print(f"Reserved judge attempts (3 per expected call): {reserved_attempts}")
        print(f"Today's judge attempts used (UTC): {today_usage} / {MAX_DAILY_QUOTA}")

        # Enforce quota check
        try:
            quota_tracker.check_quota(reserved_attempts)
        except QuotaExceededError:
            _print_run_summary(run_started, quota_tracker)
            raise

        if not auto_go:
            sys.stdout.write("Type 'go' to confirm and proceed: ")
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip().lower()
            if user_input != "go":
                print("Run aborted by user.")
                _print_run_summary(run_started, quota_tracker)
                sys.exit(0)

    consecutive_judge_failures = 0
    for arm, case in pending_tasks:
        case_started = time.perf_counter()
        print(f"Running arm [{arm.key}] on case [{case.id}] ({case.title[:45]}...)...")
        result = await run_case(
            arm,
            case,
            judge_backend=judge_backend,
            output_dir=output_dir,
            quota_tracker=quota_tracker,
            case_timeout=case_timeout,
        )
        result["duration_seconds"] = time.perf_counter() - case_started

        # Write result atomically to data/eval/<arm>/<case_id>.json
        arm_dir = output_dir / arm.key
        arm_dir.mkdir(parents=True, exist_ok=True)
        case_file = arm_dir / f"{case.id}.json"
        case_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

        all_results.append(result)
        if result.get("status") == "error":
            print(f"  -> ERROR ({result.get('error_type')}): {result.get('error')}")
        else:
            correct_flag = "✓" if result.get("outcome_correct") else "✗"
            print(
                f"  -> {correct_flag} predicted: {result.get('predicted_outcome')} "
                f"(ground truth: {result.get('ground_truth_outcome')}, "
                f"confidence: {result.get('confidence')})"
            )
        print(f"  Case elapsed: {result['duration_seconds']:.2f}s")

        if result.get("judge_failed"):
            consecutive_judge_failures += 1
        elif result.get("status") == "completed" and result.get("judge_attempts", 0) > 0:
            consecutive_judge_failures = 0

        if consecutive_judge_failures >= max_consecutive_failures:
            print(
                f"Stopping run after {consecutive_judge_failures} consecutive judge failures "
                f"(limit: {max_consecutive_failures}); latest case: {case.id}."
            )
            break

    _print_run_summary(run_started, quota_tracker)
    return all_results


def _print_run_summary(run_started: float, quota_tracker: QuotaTracker) -> None:
    """Print run duration and today's quota-charged judge request attempts."""
    print(f"Run elapsed: {time.perf_counter() - run_started:.2f}s")
    print(f"Judge attempts used today (UTC): {quota_tracker.get_today_usage()} / {MAX_DAILY_QUOTA}")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run UnitedStatesofLLMs evaluation ablation harness across cases."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--arm",
        type=str,
        help="Arm to evaluate (e.g. raw, rag, single_attacker, full_council, self_consistency, or A-E).",
    )
    group.add_argument(
        "--all-arms",
        action="store_true",
        help="Evaluate all 5 ablation arms (A through E).",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of case fixtures to evaluate.",
    )
    parser.add_argument(
        "--case-timeout",
        type=_positive_float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
        help="Wall-clock timeout for each case in seconds (default: 300).",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=_positive_int,
        default=DEFAULT_MAX_CONSECUTIVE_FAILURES,
        help="Stop after this many consecutive judge failures (default: 2).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run with mock judge; zero API quota consumed.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip case/arm pairs that already have a result saved in output directory.",
    )
    parser.add_argument(
        "--allow-mixed-results",
        action="store_true",
        help="Allow synthetic and real result files to coexist in this run.",
    )
    parser.add_argument(
        "--judge-backend",
        choices=["api", "local", "mock"],
        default=None,
        help="Judge model backend. Defaults to 'mock' if --dry-run, else 'api'.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/eval"),
        help="Directory to write results into (default: data/eval).",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=None,
        help="Custom directory to load cases from (default: evaluation/cases/dev).",
    )
    parser.add_argument(
        "--go",
        action="store_true",
        help="Skip interactive confirmation for live runs (use with caution).",
    )
    return parser


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


async def async_main(args: argparse.Namespace) -> None:
    """Async main routine."""
    # Determine judge backend
    if args.dry_run:
        judge_backend = "mock"
    elif args.judge_backend:
        judge_backend = args.judge_backend
    else:
        judge_backend = "api"

    # Resolve arms
    if args.all_arms:
        arms = [
            ARMS["raw"],
            ARMS["rag"],
            ARMS["single_attacker"],
            ARMS["full_council"],
            ARMS["self_consistency"],
        ]
    else:
        arms = [resolve_arm(args.arm)]

    # Load cases (always dev unless custom cases-dir is explicitly given)
    if args.cases_dir:
        cases = []
        for p in sorted(args.cases_dir.glob("*.json")):
            cases.append(EvaluationCase.model_validate(json.loads(p.read_text(encoding="utf-8"))))
    else:
        cases = load_cases(held_out=False)

    if args.limit is not None and args.limit > 0:
        cases = cases[: args.limit]

    quota_tracker = QuotaTracker(args.output_dir / "quota_log.json")

    await run_evaluation(
        arms=arms,
        cases=cases,
        judge_backend=judge_backend,
        output_dir=args.output_dir,
        quota_tracker=quota_tracker,
        resume=args.resume,
        auto_go=args.go,
        allow_mixed_results=args.allow_mixed_results,
        case_timeout=args.case_timeout,
        max_consecutive_failures=args.max_consecutive_failures,
    )


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(async_main(args))
    except (QuotaExceededError, KeyboardInterrupt) as exc:
        print(f"\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
