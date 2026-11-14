"""Round limits that keep the ablation ladder honest (GitHub #23).

C and D must differ only in the second attacker. When D was allowed a round C
was not, any gap between them could be the extra round, not the attacker.
"""

from __future__ import annotations

from council_core.models.debate import DebateConfig
from harness.arms import ARMS
from harness.quota import JUDGE_CALLS_PER_CASE


def test_single_and_full_council_share_a_round_ceiling() -> None:
    assert ARMS["single_attacker"].max_rounds == ARMS["full_council"].max_rounds


def test_single_pass_arms_run_one_round() -> None:
    """No attackers means nothing to argue in a second round."""
    for key in ("raw", "rag", "self_consistency"):
        assert ARMS[key].max_rounds == 1, key


def test_the_quota_budget_matches_each_arms_round_ceiling() -> None:
    """One judge call per round. A budget below the ceiling under-reserves quota;
    above it, it refuses runs that would fit."""
    for key, arm in ARMS.items():
        assert JUDGE_CALLS_PER_CASE[key] == arm.max_rounds, key


def test_the_council_is_evaluated_at_the_apps_default() -> None:
    """The evaluation scores the debate the app runs by default."""
    default = DebateConfig.model_fields["max_rounds"].default
    assert ARMS["full_council"].max_rounds == default
    for arm in ARMS.values():
        assert arm.max_rounds <= default
