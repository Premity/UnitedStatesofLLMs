"""Presenter node.

Constructs the position. In round 1 it argues from scratch; in later rounds it
rebuts the objections raised against it, which is why the prompt differs by
round.

The presenter sets the quality ceiling for the whole debate — an attacker can
only ever be as good as the argument it is given to attack — which is why this
role runs on a frontier model.
"""

from __future__ import annotations

import structlog

from app.graph.state import GraphState
from app.roles.presenter import PresenterRole

log = structlog.get_logger(__name__)


async def present(state: GraphState) -> GraphState:
    """Produce or refine the presenter's arguments for this round."""
    round_number = state.get("current_round", 0) + 1
    role = PresenterRole()

    turn = await role.run(
        config=state["config"],
        context=state.get("context", []),
        prior_arguments=state.get("arguments", []),
        prior_objections=state.get("objections", []),
        round_number=round_number,
    )

    log.info(
        "present_complete",
        run_id=state["run_id"],
        round=round_number,
        arguments=len(turn.arguments),
    )

    return {
        "current_round": round_number,
        "turns": [turn],
        "arguments": turn.arguments,
    }
