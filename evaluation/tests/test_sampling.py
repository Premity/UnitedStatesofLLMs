"""Tests for Arm E (self-consistency) and sampling machinery (T2-5).

Verifies that:
1. `self_consistency` appears in the arm registry `ARMS`.
2. Its sample count n is computed from Arm D's call count on the same case.
3. Total model calls match Arm D within ±1 across all debate lengths (1 to 3 rounds,
   and arbitrary call counts).
4. Sampling aggregation performs majority voting on outcomes with agreement rate
   as confidence, deterministic tie-breaking, and argument selection.
"""

from __future__ import annotations

import pytest

from council_core.models.debate import (
    Argument,
    DebateConfig,
    DebateState,
    Role,
    Turn,
)
from harness.arms import ARMS, Arm, SelfConsistencyArm
from harness.sampling import (
    DEFAULT_SAMPLING_TEMPERATURE,
    AggregationResult,
    PresenterSample,
    aggregate_samples,
    derive_sample_count,
    derive_sample_count_from_state,
    derive_sample_count_from_turns,
    total_calls_for_arm_e,
)


class TestArmERegistry:
    """Verifies Arm E's presence in the ablation arms registry."""

    def test_self_consistency_appears_in_registry(self) -> None:
        assert "self_consistency" in ARMS
        arm = ARMS["self_consistency"]
        assert isinstance(arm, Arm)
        assert isinstance(arm, SelfConsistencyArm)
        assert arm.key == "self_consistency"
        assert arm.retrieval_enabled is True
        assert arm.attackers == ()
        assert arm.is_single_pass is True
        assert arm.temperature == DEFAULT_SAMPLING_TEMPERATURE
        assert arm.samples is None  # Computed dynamically per case

    def test_with_samples_and_for_case(self) -> None:
        template = ARMS["self_consistency"]
        assert isinstance(template, SelfConsistencyArm)

        # Configured manually
        arm_5 = template.with_samples(5)
        assert arm_5.samples == 5
        assert arm_5.key == "self_consistency"

        # Derived from Arm D call count
        arm_d = template.for_case(d_calls=8)
        assert arm_d.samples == 7
        assert total_calls_for_arm_e(arm_d.samples, has_judge=True) == 8


class TestComputeMatchingWithArmD:
    """Proves that Arm E's total model calls match Arm D within ±1 (T2-5 core requirement)."""

    @pytest.mark.parametrize(
        ("d_rounds", "d_calls"),
        [
            (1, 4),  # 1 round: Presenter + 2 Attackers + Judge = 4
            (2, 8),  # 2 rounds: 4 * 2 = 8
            (3, 12),  # 3 rounds: 4 * 3 = 12
        ],
    )
    def test_standard_debate_rounds_match_within_one(self, d_rounds: int, d_calls: int) -> None:
        """For standard 1, 2, and 3-round debates, total calls match Arm D exactly."""
        n = derive_sample_count(d_calls, has_judge=True)
        total_e = total_calls_for_arm_e(n, has_judge=True)

        assert abs(total_e - d_calls) <= 1
        assert total_e == d_calls  # For d_calls >= 2, parity is exact!

    @pytest.mark.parametrize("d_calls", range(1, 51))
    def test_arbitrary_call_counts_match_within_one(self, d_calls: int) -> None:
        """Across any call count from 1 to 50, Arm E total calls match D within ±1."""
        n = derive_sample_count(d_calls, has_judge=True)
        total_e = total_calls_for_arm_e(n, has_judge=True)

        assert abs(total_e - d_calls) <= 1

        # Also test without judge
        n_no_judge = derive_sample_count(d_calls, has_judge=False)
        total_e_no_judge = total_calls_for_arm_e(n_no_judge, has_judge=False)
        assert abs(total_e_no_judge - d_calls) <= 1
        assert total_e_no_judge == d_calls

    def test_derive_from_turns_and_state(self) -> None:
        """Verify derivation directly from Turn collections and DebateState."""

        def make_turn(role: Role) -> Turn:
            return Turn(
                round_number=1,
                role=role,
                model_id="test_model",
                prompt_id="test_prompt",
                prompt_hash="dummy_hash",
            )

        # 4 turns matching Round 1 of Arm D
        turns = [
            make_turn(Role.PRESENTER),
            make_turn(Role.ATTACKER_DOCTRINAL),
            make_turn(Role.ATTACKER_EVIDENTIARY),
            make_turn(Role.JUDGE),
        ]

        n = derive_sample_count_from_turns(turns)
        assert n == 3
        assert total_calls_for_arm_e(n) == 4

        state = DebateState(
            config=DebateConfig(question="Test question?"),
            turns=turns * 2,  # 8 turns (2 rounds)
        )
        n_state = derive_sample_count_from_state(state)
        assert n_state == 7
        assert total_calls_for_arm_e(n_state) == 8

    def test_invalid_d_calls_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            derive_sample_count(0)
        with pytest.raises(ValueError, match="must be positive"):
            derive_sample_count(-5)
        with pytest.raises(ValueError, match="must be positive"):
            total_calls_for_arm_e(0)


class TestAggregationLogic:
    """Verifies majority-vote aggregation, agreement-rate confidence, and tie-breaking."""

    def test_unanimous_consensus(self) -> None:
        samples = [
            PresenterSample(
                sample_id=f"s_{i}",
                outcome="affirmed",
                confidence=0.85,
                arguments=[Argument(claim=f"Claim {i}", reasoning="Reason")],
            )
            for i in range(5)
        ]

        result = aggregate_samples(samples)

        assert isinstance(result, AggregationResult)
        assert result.winning_outcome == "affirmed"
        assert result.agreement_rate == 1.0  # 5 / 5
        assert result.vote_counts == {"affirmed": 5}
        assert result.total_samples == 5
        assert len(result.aggregated_arguments) == 1

    def test_majority_split_confidence(self) -> None:
        """3 affirmed vs 2 rejected -> winning outcome 'affirmed', confidence 0.6."""
        samples = [
            PresenterSample(
                sample_id="s1",
                outcome="affirmed",
                confidence=0.9,
                arguments=[Argument(claim="A1", reasoning="R1")],
            ),
            PresenterSample(
                sample_id="s2",
                outcome="affirmed",
                confidence=0.8,
                arguments=[Argument(claim="A2", reasoning="R2")],
            ),
            PresenterSample(
                sample_id="s3",
                outcome="affirmed",
                confidence=0.7,
                arguments=[Argument(claim="A3", reasoning="R3")],
            ),
            PresenterSample(
                sample_id="s4",
                outcome="rejected",
                confidence=0.6,
                arguments=[Argument(claim="R4", reasoning="R4")],
            ),
            PresenterSample(
                sample_id="s5",
                outcome="rejected",
                confidence=0.5,
                arguments=[Argument(claim="R5", reasoning="R5")],
            ),
        ]

        result = aggregate_samples(samples)

        assert result.winning_outcome == "affirmed"
        assert result.agreement_rate == 0.6  # 3 / 5
        assert result.vote_counts == {"affirmed": 3, "rejected": 2}
        assert result.selected_sample is not None
        assert result.selected_sample.sample_id == "s1"  # Highest confidence among winning
        assert result.aggregated_arguments[0].claim == "A1"

    def test_tie_breaking_by_confidence(self) -> None:
        """2 affirmed vs 2 rejected: resolved by sum of sample confidences."""
        samples = [
            PresenterSample(sample_id="s1", outcome="affirmed", confidence=0.9, arguments=[]),
            PresenterSample(
                sample_id="s2", outcome="affirmed", confidence=0.8, arguments=[]
            ),  # sum = 1.7
            PresenterSample(sample_id="s3", outcome="rejected", confidence=0.6, arguments=[]),
            PresenterSample(
                sample_id="s4", outcome="rejected", confidence=0.5, arguments=[]
            ),  # sum = 1.1
        ]

        result = aggregate_samples(samples)

        assert result.winning_outcome == "affirmed"
        assert result.agreement_rate == 0.5  # 2 / 4
        assert result.selected_sample is not None
        assert result.selected_sample.sample_id == "s1"

    def test_empty_samples_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot aggregate an empty list"):
            aggregate_samples([])
