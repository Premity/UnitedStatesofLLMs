"""Tests for the debate graph's control flow.

No model calls: these test termination logic, which is where an unbounded debate
would burn a free-tier quota in a loop.
"""

from __future__ import annotations

import pytest

from app.graph.workflow import should_continue
from council_core.models.debate import DebateConfig, Role


def config(**overrides: object) -> DebateConfig:
    base = {
        "question": "Is this a war crime?",
        "facts": "Some facts.",
        "rounds": "auto",
        "max_rounds": 3,
        "enabled_attackers": [Role.ATTACKER_DOCTRINAL, Role.ATTACKER_EVIDENTIARY],
    }
    return DebateConfig(**{**base, **overrides})


def test_stops_at_max_rounds_in_auto_mode() -> None:
    state = {"config": config(rounds="auto", max_rounds=3), "current_round": 3}
    assert should_continue(state) == "end"


def test_max_rounds_overrides_a_larger_fixed_round_count() -> None:
    """The ceiling is absolute — a config asking for more rounds cannot exceed it."""
    state = {"config": config(rounds=5, max_rounds=2), "current_round": 2}
    assert should_continue(state) == "end"


def test_continues_while_under_the_fixed_round_count() -> None:
    state = {"config": config(rounds=3, max_rounds=3), "current_round": 1}
    assert should_continue(state) == "continue"


def test_stops_at_the_fixed_round_count() -> None:
    state = {"config": config(rounds=2, max_rounds=3), "current_round": 2}
    assert should_continue(state) == "end"


def test_auto_mode_stops_when_no_novel_objections_were_raised() -> None:
    state = {
        "config": config(rounds="auto", max_rounds=3),
        "current_round": 1,
        "terminated_reason": "no_novel_objections",
    }
    assert should_continue(state) == "end"


def test_auto_mode_continues_while_objections_stay_novel() -> None:
    state = {"config": config(rounds="auto", max_rounds=3), "current_round": 1}
    assert should_continue(state) == "continue"


@pytest.mark.parametrize("rounds", [1, 2, 3])
def test_a_debate_always_terminates_within_max_rounds(rounds: int) -> None:
    """Guards against the failure that would silently drain an API quota."""
    cfg = config(rounds=rounds, max_rounds=3)
    for round_number in range(0, 10):
        if should_continue({"config": cfg, "current_round": round_number}) == "end":
            assert round_number <= cfg.max_rounds
            return
    pytest.fail("Debate did not terminate within 10 rounds.")
