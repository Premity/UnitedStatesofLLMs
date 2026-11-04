"""What the SSE stream actually emits over a multi-round debate.

The frontend drives its whole state machine off this sequence, so a duplicate
or missing event is a UI bug reported as "the frontend stopped responding".
No model calls: the graph is replaced by a scripted stream of chunks shaped
like the real one.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.routers import debate as debate_router
from app.services.run_store import RunStore
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    ObjectionDisposition,
    Role,
    Turn,
    Verdict,
)


def turn(role: Role, round_number: int) -> Turn:
    return Turn(
        round_number=round_number,
        role=role,
        model_id="test/model",
        prompt_id=f"{role.value}/test",
        prompt_hash="0" * 64,
        started_at=datetime.now(UTC),
    )


def verdict(conclusion: str) -> Verdict:
    return Verdict(
        conclusion=conclusion,
        reasoning="Because.",
        confidence=0.5,
        confidence_reasoning="Contested.",
    )


class ScriptedGraph:
    """Stands in for the compiled graph, yielding chunks the router consumes.

    `stream_mode="values"` means each chunk is the whole accumulated state, so
    `turns` grows and `verdict` persists once written — which is precisely the
    behaviour under test.
    """

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks

    def astream(self, _initial: dict[str, Any], **_kwargs: Any) -> AsyncIterator[dict]:
        async def gen() -> AsyncIterator[dict]:
            for chunk in self._chunks:
                yield chunk

        return gen()


async def collect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, chunks: list[dict[str, Any]]
) -> list[dict]:
    """Run the router over a scripted graph and return the events it emits."""
    monkeypatch.setattr(debate_router, "compiled_graph", ScriptedGraph(chunks))
    # The router persists every run, including failed ones. Keep that off the
    # real data directory — `make test` never touches anything outside tmp.
    monkeypatch.setattr(debate_router, "get_run_store", lambda: RunStore(tmp_path))

    config = DebateConfig(question="Is this a war crime?", facts="Some facts.", max_rounds=2)
    response = await debate_router.stream_debate(config)

    return [frame async for frame in response.body_iterator]


def names(events: list[dict]) -> list[str]:
    return [e["event"] for e in events]


@pytest.mark.asyncio
async def test_a_two_round_debate_emits_every_turn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r1 = [turn(Role.PRESENTER, 1), turn(Role.ATTACKER_DOCTRINAL, 1), turn(Role.JUDGE, 1)]
    r2 = [turn(Role.PRESENTER, 2), turn(Role.ATTACKER_DOCTRINAL, 2), turn(Role.JUDGE, 2)]

    events = await collect(
        monkeypatch,
        tmp_path,
        [
            {"turns": r1[:1], "current_round": 1},
            {"turns": r1[:2], "current_round": 1},
            {"turns": r1, "current_round": 1, "verdict": verdict("First holding.")},
            {"turns": r1 + r2[:1], "current_round": 2, "verdict": verdict("First holding.")},
            {"turns": r1 + r2[:2], "current_round": 2, "verdict": verdict("First holding.")},
            {"turns": r1 + r2, "current_round": 2, "verdict": verdict("Second holding.")},
        ],
    )

    assert names(events).count("turn") == 6, "every turn in both rounds reaches the client"
    assert names(events)[0] == "start"
    assert names(events)[-1] == "done"


@pytest.mark.asyncio
async def test_a_standing_verdict_is_not_re_emitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The judge rules once per round, not once per stream chunk.

    `verdict` persists in graph state, so a naive check re-sends round one's
    holding on every later chunk. The frontend treats a verdict as the court
    adjourning, which made a two-round debate look frozen after round one.
    """
    r1 = [turn(Role.PRESENTER, 1), turn(Role.JUDGE, 1)]
    r2 = [turn(Role.PRESENTER, 2), turn(Role.JUDGE, 2)]
    first, second = verdict("First holding."), verdict("Second holding.")

    events = await collect(
        monkeypatch,
        tmp_path,
        [
            {"turns": r1[:1], "current_round": 1},
            {"turns": r1, "current_round": 1, "verdict": first},
            # Round two: the same verdict is still standing in state.
            {"turns": r1 + r2[:1], "current_round": 2, "verdict": first},
            {"turns": r1 + r2, "current_round": 2, "verdict": second},
        ],
    )

    verdicts = [json.loads(e["data"]) for e in events if e["event"] == "verdict"]

    assert len(verdicts) == 2, "one verdict per ruling, not one per chunk"
    assert [v["conclusion"] for v in verdicts] == ["First holding.", "Second holding."]


@pytest.mark.asyncio
async def test_a_revised_verdict_is_emitted_even_with_the_same_conclusion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Dedupe must compare the whole verdict, not just its conclusion.

    A second round can leave the holding standing while changing what it
    survived — the dissent — and that revision has to reach the record.
    """
    objection = Objection(
        raised_by=Role.ATTACKER_DOCTRINAL,
        target_argument_id="arg_1",
        ground="Not established.",
        reasoning="The facts do not support it.",
        disposition=ObjectionDisposition.OVERRULED,
    )

    first = verdict("Same holding.")
    revised = verdict("Same holding.")
    revised.dissent = [objection]

    events = await collect(
        monkeypatch,
        tmp_path,
        [
            {"turns": [turn(Role.JUDGE, 1)], "current_round": 1, "verdict": first},
            {"turns": [turn(Role.JUDGE, 1)], "current_round": 1, "verdict": first},
            {"turns": [turn(Role.JUDGE, 2)], "current_round": 2, "verdict": revised},
        ],
    )

    verdicts = [json.loads(e["data"]) for e in events if e["event"] == "verdict"]

    assert len(verdicts) == 2
    assert len(verdicts[1]["dissent"]) == 1


@pytest.mark.asyncio
async def test_arguments_carry_through_rounds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A later round's turns must not be withheld because earlier ones were seen."""
    argument = Argument(claim="A claim.", reasoning="Because.")
    t1, t2 = turn(Role.PRESENTER, 1), turn(Role.PRESENTER, 2)
    t2.arguments = [argument]

    events = await collect(
        monkeypatch,
        tmp_path,
        [
            {"turns": [t1], "current_round": 1},
            {"turns": [t1, t2], "current_round": 2},
        ],
    )

    emitted = [json.loads(e["data"]) for e in events if e["event"] == "turn"]
    assert [t["round_number"] for t in emitted] == [1, 2]
    assert emitted[1]["arguments"][0]["claim"] == "A claim."
