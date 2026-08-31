"""Attacker nodes.

Two attackers, separated by mandate rather than capability:

  doctrinal    challenges the legal characterisation — proportionality,
               distinction, command responsibility, elements of the crime
  evidentiary  challenges the factual predicate — sufficiency of evidence,
               inference of mens rea, attribution

They run in parallel and each returns only `turns` and `objections`, which the
`operator.add` reducers merge. Returning the full state here would raise
`InvalidUpdateError`.

The overlap between their objection sets is itself a measured quantity — see
`evaluation/metrics/independence.py`. High overlap would mean the second
attacker is not earning its place.
"""

from __future__ import annotations

import structlog

from app.graph.state import GraphState
from app.roles.attacker import AttackerRole
from council_core.models.debate import Role

log = structlog.get_logger(__name__)


async def _attack(state: GraphState, role_name: Role) -> GraphState:
    """Shared attacker body. Both nodes differ only by mandate and model."""
    config = state["config"]

    if role_name not in config.enabled_attackers:
        log.info("attacker_disabled", run_id=state["run_id"], role=role_name.value)
        return {}

    role = AttackerRole(role_name)
    turn = await role.run(
        config=config,
        context=state.get("context", []),
        arguments=state.get("arguments", []),
        round_number=state.get("current_round", 1),
    )

    log.info(
        "attack_complete",
        run_id=state["run_id"],
        role=role_name.value,
        objections=len(turn.objections),
    )

    return {"turns": [turn], "objections": turn.objections}


async def attack_doctrinal(state: GraphState) -> GraphState:
    """Challenge the legal characterisation."""
    return await _attack(state, Role.ATTACKER_DOCTRINAL)


async def attack_evidentiary(state: GraphState) -> GraphState:
    """Challenge the factual predicate."""
    return await _attack(state, Role.ATTACKER_EVIDENTIARY)
