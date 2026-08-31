"""The debate graph.

    START
      -> retrieve            ground the question in the corpus
      -> present             presenter states the position
      -> [attack_doctrinal, attack_evidentiary]      (parallel fan-out)
      -> judge               rules on every objection
      -> continue? --yes--> present   (next round)
                   --no---> END

The two attackers run concurrently: they read the same arguments and write
disjoint objections, so there is no reason to serialise them. LangGraph holds
`judge` until both finish.

Round control lives in `should_continue`. In `auto` mode the judge decides
whether the last round produced anything novel; in fixed mode the count decides.
Both are bounded by `config.max_rounds` — a debate that cannot terminate is a
bug.

The compiled graph is a module-level singleton built at import. Adding or
renaming a node means editing `build_graph()` and restarting the server.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from app.graph.nodes.attack import attack_doctrinal, attack_evidentiary
from app.graph.nodes.judge import judge
from app.graph.nodes.present import present
from app.graph.nodes.retrieve import retrieve
from app.graph.state import GraphState
from council_core.models.debate import Role

log = structlog.get_logger(__name__)


def should_continue(state: GraphState) -> str:
    """Decide whether to run another round or finish.

    Returns the name of the next node, which LangGraph maps through the
    conditional edge below.
    """
    config = state["config"]
    current = state.get("current_round", 0)

    if current >= config.max_rounds:
        log.info("debate_terminated", reason="max_rounds", rounds=current)
        return "end"

    if isinstance(config.rounds, int):
        return "continue" if current < config.rounds else "end"

    # auto mode — the judge sets terminated_reason when nothing novel was raised
    if state.get("terminated_reason") == "no_novel_objections":
        log.info("debate_terminated", reason="no_novel_objections", rounds=current)
        return "end"

    return "continue"


def build_graph() -> StateGraph:
    """Construct and compile the debate graph."""
    graph = StateGraph(GraphState)

    graph.add_node("retrieve", retrieve)
    graph.add_node("present", present)
    graph.add_node(Role.ATTACKER_DOCTRINAL.value, attack_doctrinal)
    graph.add_node(Role.ATTACKER_EVIDENTIARY.value, attack_evidentiary)
    graph.add_node("judge", judge)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "present")

    # Fan out: both attackers read the presenter's arguments concurrently.
    graph.add_edge("present", Role.ATTACKER_DOCTRINAL.value)
    graph.add_edge("present", Role.ATTACKER_EVIDENTIARY.value)

    # Fan in: LangGraph holds judge until both attackers complete.
    graph.add_edge(Role.ATTACKER_DOCTRINAL.value, "judge")
    graph.add_edge(Role.ATTACKER_EVIDENTIARY.value, "judge")

    graph.add_conditional_edges(
        "judge",
        should_continue,
        {"continue": "present", "end": END},
    )

    return graph.compile()


compiled_graph = build_graph()
"""Singleton compiled at import time."""
