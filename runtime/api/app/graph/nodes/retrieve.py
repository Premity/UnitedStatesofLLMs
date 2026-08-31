"""Retrieval node — grounds the debate in the corpus.

Runs once, before the first round. Every role reads the same retrieved context,
so the presenter and its attackers argue over the same authority rather than
each retrieving their own convenient subset.

When `config.retrieval_enabled` is False this is a no-op, which is how the
ungrounded ablation arm is produced.
"""

from __future__ import annotations

import structlog

from app.graph.state import GraphState
from app.services.retrieval import get_retrieval_service

log = structlog.get_logger(__name__)


async def retrieve(state: GraphState) -> GraphState:
    """Fetch corpus spans relevant to the question."""
    config = state["config"]

    if not config.retrieval_enabled:
        log.info("retrieval_skipped", run_id=state["run_id"])
        return {"context": []}

    service = get_retrieval_service()
    query = f"{config.question}\n\n{config.facts}".strip()
    context = await service.search(query, top_k=config.top_k)

    log.info("retrieval_complete", run_id=state["run_id"], spans=len(context))
    return {"context": context}
