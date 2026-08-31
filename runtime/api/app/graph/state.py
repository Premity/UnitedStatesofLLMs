"""LangGraph state channels.

`DebateState` (the Pydantic model in council_core) is the domain object. This
module adapts it to LangGraph's `TypedDict` + reducer convention.

The reducers matter. The two attackers run in parallel and both append to
`turns` and `objections`; `operator.add` merges their lists instead of one
clobbering the other. Channels a single node owns use the default last-write
reducer.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from council_core.models.citation import ResolvedCitation
from council_core.models.debate import Argument, DebateConfig, Objection, Turn, Verdict


class GraphState(TypedDict, total=False):
    """Channels shared by every node in the debate graph.

    IMPORTANT: a node must return ONLY the keys it writes. Returning the whole
    state from a parallel node raises `InvalidUpdateError` — two concurrent
    writers to a single-value channel is an error, even when the values match.
    """

    run_id: str
    config: DebateConfig

    context: list[ResolvedCitation]

    current_round: int
    turns: Annotated[list[Turn], operator.add]
    arguments: Annotated[list[Argument], operator.add]
    objections: Annotated[list[Objection], operator.add]

    verdict: Verdict | None
    terminated_reason: str | None
