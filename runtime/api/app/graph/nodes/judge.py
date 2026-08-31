"""Judge node.

Rules on every objection, synthesises the surviving arguments, and calibrates a
confidence. The overruled objections become the dissent log — so the judge is
required to state a reason for each rejection, not merely a disposition.

In `auto` round mode the judge also reports whether the round produced novel
objections; that flag is what lets the debate terminate early.
"""

from __future__ import annotations

import structlog

from app.graph.state import GraphState
from app.roles.judge import JudgeRole

log = structlog.get_logger(__name__)


async def judge(state: GraphState) -> GraphState:
    """Rule on the round and produce (or update) the verdict."""
    role = JudgeRole()

    turn, verdict, novel = await role.run(
        config=state["config"],
        context=state.get("context", []),
        arguments=state.get("arguments", []),
        objections=state.get("objections", []),
        round_number=state.get("current_round", 1),
    )

    log.info(
        "judge_complete",
        run_id=state["run_id"],
        round=state.get("current_round", 1),
        confidence=verdict.confidence,
        dissent=len(verdict.dissent),
        novel_objections=novel,
    )

    update: GraphState = {"turns": [turn], "verdict": verdict}
    if not novel:
        update["terminated_reason"] = "no_novel_objections"

    return update
