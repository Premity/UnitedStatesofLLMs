"""Tests for evaluation harness runner and quota tracking (T4-1).

Tests:
1. QuotaTracker enforcement and accounting.
2. CLI argument parsing and arm resolution.
3. Outcome normalization.
4. Dry-run execution with mock judge (zero quota).
5. Resume behavior (skipping existing output).
6. Limit behavior.
7. Arm E self-consistency execution in harness.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from council_core.llm import client as llm_client
from council_core.models.debate import Argument, Role, Turn, Verdict
from harness.arms import ARMS
from harness.cases import EvaluationCase, Outcome
from harness.quota import (
    QuotaExceededError,
    QuotaTracker,
    get_expected_calls,
)
from harness.run import (
    MockJudgeRole,
    build_parser,
    normalize_outcome,
    resolve_arm,
    run_case,
    run_evaluation,
)
from metrics.provenance import MixedResultProvenanceError, load_result_files


@pytest.fixture
def temp_eval_dir(tmp_path: Path) -> Path:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    return eval_dir


@pytest.fixture
def sample_case() -> EvaluationCase:
    return EvaluationCase(
        id="test_case_1",
        title="Test Case 1",
        court="ICTY",
        year=2003,
        question="Does sustained shelling of civilians constitute a war crime?",
        facts="Sustained shelling targeted civilians without military necessity.",
        holding="Held that sustained shelling constitutes a war crime.",
        outcome=Outcome.AFFIRMED,
        key_reasoning=["Shelling was deliberate"],
        difficulty="medium",
        source_case_id="icty_test",
    )


def _make_turn(role: Role, round_number: int = 1, arguments: list[Argument] | None = None) -> Turn:
    return Turn(
        role=role,
        round_number=round_number,
        model_id="test_model",
        prompt_id="test_prompt",
        prompt_hash="dummy_hash",
        arguments=arguments or [],
    )


class TestQuotaTracking:
    """Verifies quota limits and daily accounting."""

    def test_expected_calls_per_arm(self) -> None:
        assert get_expected_calls("raw", 1) == 1
        assert get_expected_calls("rag", 1) == 1
        assert get_expected_calls("single_attacker", 1) == 2
        assert get_expected_calls("full_council", 1) == 3
        assert get_expected_calls("self_consistency", 1) == 1

        # Multiple cases
        assert get_expected_calls("full_council", 4) == 12

    def test_quota_tracker_records_calls_and_enforces_limit(self, temp_eval_dir: Path) -> None:
        log_path = temp_eval_dir / "quota_log.json"
        tracker = QuotaTracker(log_path)

        assert tracker.get_today_usage() == 0

        # Record 10 calls
        tracker.record_call(case_id="case_1", arm_key="full_council", calls=3)
        tracker.record_call(case_id="case_2", arm_key="full_council", calls=3)
        tracker.record_call(case_id="case_3", arm_key="full_council", calls=3)
        assert tracker.get_today_usage() == 9

        # Quota check passes when under 40
        allowed, used, remaining = tracker.check_quota(expected_calls=10)
        assert allowed is True
        assert used == 9
        assert remaining == 21

        # Exceeding 40 raises QuotaExceededError
        with pytest.raises(QuotaExceededError, match="exceeds the daily safety limit of 40"):
            tracker.check_quota(expected_calls=32)

    def test_zero_calls_do_not_modify_quota_log(self, temp_eval_dir: Path) -> None:
        log_path = temp_eval_dir / "quota_log.json"
        tracker = QuotaTracker(log_path)

        tracker.record_call(case_id="case_mock", arm_key="rag", calls=0, backend="mock")
        assert tracker.get_today_usage() == 0
        data = tracker.load()
        assert len(data["history"]) == 1
        assert data["history"][0]["backend"] == "mock"
        assert data["history"][0]["calls"] == 0
        assert data["history"][0]["attempts"] == 0

    def test_quota_log_records_each_request_attempt(self, temp_eval_dir: Path) -> None:
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        tracker.record_call(
            case_id="case_retry",
            arm_key="raw",
            calls=3,
            attempts=3,
            failures=2,
            backend="api",
        )

        assert tracker.get_today_usage() == 3
        data = tracker.load()
        assert data["daily_usage"][tracker._today_utc()]["attempts"] == 3
        assert data["history"][-1]["attempts"] == 3
        assert data["history"][-1]["failures"] == 2

    def test_quota_tracker_reads_legacy_daily_call_counts(self, temp_eval_dir: Path) -> None:
        log_path = temp_eval_dir / "quota_log.json"
        tracker = QuotaTracker(log_path)
        today = tracker._today_utc()
        log_path.write_text(
            json.dumps({"daily_usage": {today: {"calls": 5}}, "history": []}),
            encoding="utf-8",
        )

        tracker.record_call("new_case", "raw", calls=2, attempts=2, backend="api")

        assert tracker.get_today_usage() == 7

    @pytest.mark.asyncio
    async def test_refuses_api_run_when_quota_would_exceed_40(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        log_path = temp_eval_dir / "quota_log.json"
        tracker = QuotaTracker(log_path)
        tracker.record_call(case_id="prior_case", arm_key="full_council", calls=39)
        assert tracker.get_today_usage() == 39

        # Arm D needs 3 calls. 39 + 3 = 42 > 40.
        arm = ARMS["full_council"]
        with (
            patch("harness.run.run_case", AsyncMock()) as run_case_mock,
            pytest.raises(QuotaExceededError, match="exceeds the daily safety limit of 40"),
        ):
            await run_evaluation(
                arms=[arm],
                cases=[sample_case],
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                auto_go=True,
            )

        run_case_mock.assert_not_awaited()
        assert tracker.get_today_usage() == 39

    @pytest.mark.asyncio
    async def test_reserves_three_attempts_per_expected_judge_call(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")
        tracker.record_call(case_id="prior_case", arm_key="raw", calls=38)

        with (
            patch("harness.run.run_case", AsyncMock()) as run_case_mock,
            pytest.raises(QuotaExceededError, match="Projected total 41"),
        ):
            await run_evaluation(
                arms=[ARMS["raw"]],
                cases=[sample_case],
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                auto_go=True,
            )

        run_case_mock.assert_not_awaited()
        assert tracker.get_today_usage() == 38

    @pytest.mark.asyncio
    async def test_failed_judge_call_is_counted_against_quota(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        async def fail_after_request(_: dict) -> None:
            llm_client.log.info("llm_request", role="judge", model="test")
            raise RuntimeError("judge provider request failed")

        with patch(
            "harness.run.compiled_graph.ainvoke",
            AsyncMock(side_effect=fail_after_request),
        ):
            result = await run_case(
                arm=ARMS["raw"],
                case=sample_case,
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
            )

        assert result["error"] == "judge provider request failed"
        assert result["status"] == "error"
        assert result["outcome_correct"] is None
        assert result["judge_attempts"] == 1
        assert result["judge_failures"] == 1
        assert result["judge_failed"] is True
        assert tracker.get_today_usage() == 1
        history = tracker.load()["history"]
        assert history[-1]["backend"] == "api"
        assert history[-1]["calls"] == 1
        assert history[-1]["attempts"] == 1

    @pytest.mark.asyncio
    async def test_retries_and_structured_repairs_are_counted_as_attempts(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")
        final_state = {
            "current_round": 1,
            "turns": [_make_turn(Role.JUDGE)],
            "arguments": [],
            "objections": [],
            "context": [],
            "verdict": Verdict(conclusion="affirmed", reasoning="Reason", confidence=0.8),
        }

        async def return_after_attempts(_: dict) -> dict:
            for attempt in range(3):
                llm_client.log.info("llm_request", role="judge", model="test")
                if attempt == 1:
                    llm_client.log.warning("structured_output_repair", role="judge", attempt=1)
                if attempt:
                    llm_client.log.info("llm_response", role="judge", model="test")
            llm_client.log.info("llm_request", role="presenter", model="test")
            return final_state

        with patch(
            "harness.run.compiled_graph.ainvoke",
            AsyncMock(side_effect=return_after_attempts),
        ):
            result = await run_case(
                arm=ARMS["raw"],
                case=sample_case,
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
            )

        assert result["status"] == "completed"
        assert result["judge_attempts"] == 3
        assert result["judge_failures"] == 1
        assert result["judge_failed"] is False
        assert tracker.get_today_usage() == 3
        assert tracker.load()["history"][-1]["attempts"] == 3


class TestCliAndArmResolution:
    """Verifies CLI argument parsing and arm lookup."""

    @pytest.mark.parametrize(
        ("input_arm", "expected_key"),
        [
            ("raw", "raw"),
            ("A", "raw"),
            ("rag", "rag"),
            ("B", "rag"),
            ("single_attacker", "single_attacker"),
            ("c", "single_attacker"),
            ("full_council", "full_council"),
            ("D", "full_council"),
            ("self_consistency", "self_consistency"),
            ("E", "self_consistency"),
        ],
    )
    def test_resolve_arm_aliases(self, input_arm: str, expected_key: str) -> None:
        arm = resolve_arm(input_arm)
        assert arm.key == expected_key

    def test_resolve_unknown_arm_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown arm 'nonexistent'"):
            resolve_arm("nonexistent")

    def test_cli_parser_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--arm", "rag"])
        assert args.arm == "rag"
        assert args.dry_run is False
        assert args.resume is False
        assert args.limit is None
        assert args.judge_backend is None
        assert args.case_timeout == 300
        assert args.max_consecutive_failures == 2

    def test_cli_parser_dry_run_and_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--arm", "B", "--dry-run", "--limit", "2", "--resume"])
        assert args.arm == "B"
        assert args.dry_run is True
        assert args.limit == 2
        assert args.resume is True
        assert args.allow_mixed_results is False

    def test_cli_parser_allows_explicit_mixed_results(self) -> None:
        args = build_parser().parse_args(["--arm", "rag", "--allow-mixed-results"])
        assert args.allow_mixed_results is True

    def test_cli_parser_timeout_and_failure_limit(self) -> None:
        args = build_parser().parse_args(
            ["--arm", "rag", "--case-timeout", "12.5", "--max-consecutive-failures", "4"]
        )
        assert args.case_timeout == 12.5
        assert args.max_consecutive_failures == 4

    @pytest.mark.parametrize(
        ("flag", "value"),
        [("--case-timeout", "0"), ("--max-consecutive-failures", "0")],
    )
    def test_cli_parser_rejects_non_positive_limits(self, flag: str, value: str) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--arm", "rag", flag, value])


class TestOutcomeNormalization:
    """Verifies free-text conclusion mapping to standard outcomes."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("affirmed", "affirmed"),
            ("AFFIRMED", "affirmed"),
            ("The Trial Chamber holds that this constitutes a violation.", "affirmed"),
            ("Conduct is prohibited under international humanitarian law.", "affirmed"),
            ("rejected", "rejected"),
            ("The charges are dismissed; this does not constitute a war crime.", "rejected"),
            ("indeterminate", "indeterminate"),
            (None, "indeterminate"),
            ("Unknown holding", "indeterminate"),
        ],
    )
    def test_normalize_outcome(self, text: str | None, expected: str) -> None:
        assert normalize_outcome(text) == expected


class TestHarnessExecution:
    """Verifies running arms with mock judge (dry-run)."""

    @pytest.mark.asyncio
    async def test_mock_judge_role(self) -> None:
        mock_judge = MockJudgeRole()
        turn, verdict, novel = await mock_judge.run(
            config=sample_case,  # type: ignore[arg-type]
            context=[],
            arguments=[Argument(claim="Claim 1", reasoning="Reason 1")],
            objections=[],
            round_number=1,
        )
        assert turn.role == Role.JUDGE
        assert verdict.conclusion == "affirmed"
        assert verdict.confidence == 0.85
        assert novel is False

    @pytest.mark.asyncio
    async def test_run_case_dry_run_writes_result(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        arm = ARMS["rag"]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        mock_final_state = {
            "current_round": 1,
            "turns": [
                _make_turn(Role.PRESENTER, round_number=1),
                _make_turn(Role.JUDGE, round_number=1),
            ],
            "arguments": [Argument(claim="Claim", reasoning="Reason")],
            "objections": [],
            "context": [],
            "verdict": Verdict(
                conclusion="affirmed",
                reasoning="Affirmed by mock judge.",
                confidence=0.85,
            ),
        }

        with patch("harness.run.compiled_graph.ainvoke", AsyncMock(return_value=mock_final_state)):
            result = await run_case(
                arm=arm,
                case=sample_case,
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
            )

        assert result["case_id"] == "test_case_1"
        assert result["arm"] == "rag"
        assert result["judge_backend"] == "mock"
        assert result["judge_calls"] == 0  # Zero quota used
        assert result["predicted_outcome"] == "affirmed"
        assert result["outcome_correct"] is True
        assert result["confidence"] == 0.85
        assert "prompt_hashes" in result
        assert result["synthetic"] is True
        assert tracker.get_today_usage() == 0  # Zero quota logged

    @pytest.mark.asyncio
    async def test_run_evaluation_resume_and_limit(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        arm = ARMS["rag"]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        case_2 = EvaluationCase(
            id="test_case_2",
            title="Test Case 2",
            court="ICTY",
            year=2004,
            question="Question 2?",
            facts="Facts 2",
            holding="Holding 2",
            outcome=Outcome.AFFIRMED,
        )

        mock_final_state = {
            "current_round": 1,
            "turns": [_make_turn(Role.PRESENTER, round_number=1)],
            "arguments": [],
            "objections": [],
            "context": [],
            "verdict": Verdict(conclusion="affirmed", reasoning="Reason", confidence=0.8),
        }

        with patch("harness.run.compiled_graph.ainvoke", AsyncMock(return_value=mock_final_state)):
            # Run with limit = 1
            results = await run_evaluation(
                arms=[arm],
                cases=[sample_case, case_2],
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                resume=False,
                auto_go=True,
            )

        # File exists for test_case_1 and test_case_2
        assert (temp_eval_dir / "rag" / "test_case_1.json").exists()
        assert (temp_eval_dir / "rag" / "test_case_2.json").exists()
        assert (
            json.loads((temp_eval_dir / "rag" / "test_case_1.json").read_text())["synthetic"]
            is True
        )
        assert len(results) == 2

        # Second run with resume=True should skip both
        with patch("harness.run.run_case", AsyncMock()) as run_case_mock:
            resumed = await run_evaluation(
                arms=[arm],
                cases=[sample_case, case_2],
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                resume=True,
                auto_go=True,
            )
            assert len(resumed) == 2
            run_case_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_timeout_is_saved_and_retried_by_resume(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        arm = ARMS["raw"]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        async def slow_graph(_: dict) -> dict:
            await asyncio.sleep(0.05)
            return {}

        with patch("harness.run.compiled_graph.ainvoke", AsyncMock(side_effect=slow_graph)):
            failed = await run_evaluation(
                arms=[arm],
                cases=[sample_case],
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                case_timeout=0.005,
                auto_go=True,
            )

        result_file = temp_eval_dir / "raw" / f"{sample_case.id}.json"
        saved = json.loads(result_file.read_text(encoding="utf-8"))
        assert failed[0]["status"] == "error"
        assert saved["error_type"] == "timeout"
        assert saved["outcome_correct"] is None

        final_state = {
            "current_round": 1,
            "turns": [_make_turn(Role.JUDGE)],
            "arguments": [],
            "objections": [],
            "context": [],
            "verdict": Verdict(conclusion="affirmed", reasoning="Reason", confidence=0.8),
        }
        with patch(
            "harness.run.compiled_graph.ainvoke",
            AsyncMock(return_value=final_state),
        ) as retry_mock:
            retried = await run_evaluation(
                arms=[arm],
                cases=[sample_case],
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                resume=True,
                auto_go=True,
            )

        retry_mock.assert_awaited_once()
        assert retried[0]["status"] == "completed"
        assert json.loads(result_file.read_text(encoding="utf-8"))["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stops_after_consecutive_judge_failures(
        self,
        temp_eval_dir: Path,
        sample_case: EvaluationCase,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cases = [
            sample_case,
            sample_case.model_copy(update={"id": "test_case_2"}),
            sample_case.model_copy(update={"id": "test_case_3"}),
        ]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        async def fail_judge(_: dict) -> None:
            llm_client.log.info("llm_request", role="judge", model="test")
            raise RuntimeError("judge request failed")

        with patch(
            "harness.run.compiled_graph.ainvoke",
            AsyncMock(side_effect=fail_judge),
        ) as graph_mock:
            results = await run_evaluation(
                arms=[ARMS["raw"]],
                cases=cases,
                judge_backend="api",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                auto_go=True,
            )

        assert graph_mock.await_count == 2
        assert len(results) == 2
        assert all(result["status"] == "error" for result in results)
        assert not (temp_eval_dir / "raw" / "test_case_3.json").exists()
        output = capsys.readouterr().out
        assert "Stopping run after 2 consecutive judge failures" in output
        assert "Case elapsed:" in output
        assert "Run elapsed:" in output
        assert "Judge attempts used today (UTC): 2 / 40" in output

    @pytest.mark.asyncio
    async def test_harness_rejects_mixed_results_unless_explicitly_allowed(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        raw_dir = temp_eval_dir / "raw"
        raw_dir.mkdir(parents=True)
        (raw_dir / "prior_case.json").write_text(
            json.dumps({"judge_backend": "api", "synthetic": False}),
            encoding="utf-8",
        )
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        with pytest.raises(MixedResultProvenanceError, match="both synthetic and real"):
            await run_evaluation(
                arms=[ARMS["rag"]],
                cases=[sample_case],
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                auto_go=True,
            )

        results = await run_evaluation(
            arms=[ARMS["rag"]],
            cases=[sample_case],
            judge_backend="mock",
            output_dir=temp_eval_dir,
            quota_tracker=tracker,
            auto_go=True,
            allow_mixed_results=True,
        )
        assert len(results) == 1
        assert results[0]["synthetic"] is True
        assert len(load_result_files(temp_eval_dir, allow_mixed_results=True)) == 2

    @pytest.mark.asyncio
    async def test_judge_backend_recorded_in_result_and_quota_log(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        arm = ARMS["raw"]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        mock_final_state = {
            "current_round": 1,
            "turns": [_make_turn(Role.PRESENTER, round_number=1)],
            "arguments": [],
            "objections": [],
            "context": [],
            "verdict": Verdict(conclusion="affirmed", reasoning="Reason", confidence=0.8),
        }

        with patch("harness.run.compiled_graph.ainvoke", AsyncMock(return_value=mock_final_state)):
            results = await run_evaluation(
                arms=[arm],
                cases=[sample_case],
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
                auto_go=True,
            )

        assert len(results) == 1
        res = results[0]
        assert res["judge_backend"] == "mock"
        assert res["citation_statuses"]["total"] == 0

        # Verify in quota_log.json
        quota_data = tracker.load()
        assert len(quota_data["history"]) >= 1
        assert quota_data["history"][-1]["backend"] == "mock"
        assert quota_data["history"][-1]["calls"] == 0


class TestArmEHarness:
    """Verifies Arm E self-consistency execution in run.py."""

    @pytest.mark.asyncio
    async def test_arm_e_derives_samples_and_aggregates(
        self, temp_eval_dir: Path, sample_case: EvaluationCase
    ) -> None:
        arm = ARMS["self_consistency"]
        tracker = QuotaTracker(temp_eval_dir / "quota_log.json")

        # Create mock Arm D result with 8 total calls (2 rounds)
        d_dir = temp_eval_dir / "full_council"
        d_dir.mkdir(parents=True, exist_ok=True)
        (d_dir / f"{sample_case.id}.json").write_text(
            json.dumps({"total_calls": 8, "turns": [{}] * 8}),
            encoding="utf-8",
        )

        mock_presenter_turn = _make_turn(
            Role.PRESENTER,
            round_number=1,
            arguments=[Argument(claim="Deliberate shelling is prohibited", reasoning="Reason")],
        )

        mock_retrieval = AsyncMock()
        mock_retrieval.search = AsyncMock(return_value=[])

        with (
            patch("harness.run.get_retrieval_service", return_value=mock_retrieval),
            patch(
                "app.roles.presenter.PresenterRole.run", AsyncMock(return_value=mock_presenter_turn)
            ),
        ):
            result = await run_case(
                arm=arm,
                case=sample_case,
                judge_backend="mock",
                output_dir=temp_eval_dir,
                quota_tracker=tracker,
            )

        assert result["arm"] == "self_consistency"
        # 8 Arm D calls -> n = 7 presenter samples
        assert result["samples"] == 7
        assert result["judge_calls"] == 0
        assert result["outcome_correct"] is True
        assert result["confidence"] == 1.0  # All samples agree on affirmed
