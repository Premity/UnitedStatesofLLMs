"""Debate endpoints — start a run, stream it, read the result.

Turn-level SSE rather than token streaming. A four-model debate takes minutes,
and what a viewer wants to see is "the doctrinal attacker raised three
objections", not tokens trickling out of a 12B model. Turn events are also what
the courtroom frontend animates against.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_role_models, get_settings
from app.graph.workflow import compiled_graph
from app.services.run_store import get_run_store
from council_core.models.debate import DebateConfig, DebateState, Role
from council_core.models.run import RunArtifact, RunMetadata, RunStatus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/debate", tags=["debate"])

# Which task names are reported as `role_started`.
#
# Derived from `Role`, not hand-listed: a node whose name is not a role (a
# future router or aggregator) is internal to the graph and means nothing to
# a courtroom, while every node that *is* a role should report without anyone
# remembering to add it here.
#
# Two nodes are named for the work rather than the worker -- `retrieve` and
# `present` -- so they are mapped onto the role the courtroom shows. The guard
# test `test_every_graph_node_is_either_a_streamed_role_or_deliberately_not`
# fails if a node is added that is neither a role name nor listed here, which
# is the moment to decide whether the courtroom should announce it.
_TASK_ROLE_ALIASES = {
    "retrieve": Role.RETRIEVER.value,
    "present": Role.PRESENTER.value,
}
STREAMED_ROLES = frozenset({r.value for r in Role} | set(_TASK_ROLE_ALIASES))

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Bounds concurrent debates.

    Three of the four roles run on free-tier quotas; unbounded concurrency
    exhausts them and every in-flight run fails together.
    """
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(get_settings().max_concurrent_debates)
    return _semaphore


def _initial_metadata(run_id: str) -> RunMetadata:
    """Record which models and settings this run actually used."""
    models = get_role_models()
    return RunMetadata(
        run_id=run_id,
        status=RunStatus.RUNNING,
        role_models={
            role: models.for_role(role).model_id
            for role in (
                "presenter",
                "attacker_doctrinal",
                "attacker_evidentiary",
                "judge",
            )
        },
        temperatures={
            role: models.for_role(role).temperature
            for role in (
                "presenter",
                "attacker_doctrinal",
                "attacker_evidentiary",
                "judge",
            )
        },
        seed=models.seed,
    )


@router.post("/stream")
async def stream_debate(config: DebateConfig) -> EventSourceResponse:
    """Run a debate, streaming turn-level events as they complete.

    Event types:
        `role_started`  a node began — carries {role, round}
        `turn`          one role finished — carries the full Turn object
        `verdict`       the judge ruled
        `done`          the run finished — carries run_id and the final state
        `error`         the run failed
    """
    state = DebateState(config=config)
    metadata = _initial_metadata(state.run_id)
    store = get_run_store()

    async def events() -> AsyncIterator[dict[str, str]]:
        started = datetime.now(UTC)
        seen_turns = 0
        last_verdict: str | None = None

        yield {"event": "start", "data": json.dumps({"run_id": state.run_id})}

        async with _get_semaphore():
            try:
                # Two stream modes, not one.
                #
                # `values` carries completed state, which is what a turn is
                # built from. It cannot say that a node *began* -- a snapshot
                # only exists once a node has written to state. The frontend
                # needs that signal: a turn runs 40 to 90 seconds, so most of
                # a debate is spent waiting on a role that has produced
                # nothing yet, and "who are we waiting on" is the one thing
                # worth showing meanwhile.
                #
                # `tasks` supplies it. A task event with no `result` key is a
                # start; one with `result` is a finish, which `values` already
                # covers. Node names are `Role` values (see `build_graph`), so
                # the graph itself reports who is working -- replacing a
                # hand-maintained copy of the graph's shape in the frontend
                # store that nothing kept in sync.
                async for mode, chunk in compiled_graph.astream(
                    {"run_id": state.run_id, "config": config, "current_round": 0},
                    stream_mode=["values", "tasks"],
                ):
                    if mode == "tasks":
                        # Finishes are redundant with the `turn` event.
                        if isinstance(chunk, dict) and "result" not in chunk:
                            name = chunk.get("name")
                            role = _TASK_ROLE_ALIASES.get(name, name)
                            if role in STREAMED_ROLES:
                                yield {
                                    "event": "role_started",
                                    "data": json.dumps(
                                        {"role": role, "round": state.current_round}
                                    ),
                                }
                        continue

                    turns = chunk.get("turns", [])

                    # Emit only turns the client has not seen yet.
                    for turn in turns[seen_turns:]:
                        yield {
                            "event": "turn",
                            "data": turn.model_dump_json(),
                        }
                    seen_turns = len(turns)

                    # `verdict` is a single-value channel: once the judge
                    # writes it, it stands in state for every later chunk. Only
                    # emit it when it has actually changed, or a multi-round
                    # debate re-sends round one's holding on each chunk and the
                    # client — which reads a verdict as the court adjourning —
                    # stops following the run.
                    if (verdict := chunk.get("verdict")) is not None:
                        payload = verdict.model_dump_json()
                        if payload != last_verdict:
                            last_verdict = payload
                            yield {"event": "verdict", "data": payload}

                    state.turns = turns
                    state.arguments = chunk.get("arguments", [])
                    state.objections = chunk.get("objections", [])
                    state.context = chunk.get("context", [])
                    state.current_round = chunk.get("current_round", 0)
                    state.verdict = chunk.get("verdict")
                    state.terminated_reason = chunk.get("terminated_reason")

                metadata.status = RunStatus.COMPLETED

            except Exception as exc:
                log.exception("debate_failed", run_id=state.run_id)
                metadata.status = RunStatus.FAILED
                metadata.error = str(exc)
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}

            finally:
                metadata.completed_at = datetime.now(UTC)
                metadata.duration_seconds = (metadata.completed_at - started).total_seconds()
                metadata.total_prompt_tokens = sum(t.prompt_tokens or 0 for t in state.turns)
                metadata.total_completion_tokens = sum(
                    t.completion_tokens or 0 for t in state.turns
                )
                store.save(RunArtifact(metadata=metadata, state=state))

        yield {
            "event": "done",
            "data": json.dumps({"run_id": state.run_id, "status": metadata.status.value}),
        }

    # sse-starlette's default frame separator is "\r\n\r\n". The frontend
    # splits incoming frames on "\n\n" (useDebateStream.ts), which never
    # matches that separator -- every event stays buffered until the stream
    # ends and nothing renders live. Match the frontend's expectation instead
    # of changing it, since "\n\n" is the separator the SSE spec itself uses.
    return EventSourceResponse(events(), sep="\n")


@router.get("/runs")
async def list_runs(limit: int = 50) -> list[RunMetadata]:
    """Recent runs, newest first."""
    return [a.metadata for a in get_run_store().list_runs(limit=limit)]


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunArtifact:
    """One complete run artifact."""
    artifact = get_run_store().load(run_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return artifact


@router.get("/runs/{run_id}/export.md", response_class=PlainTextResponse)
async def export_markdown(run_id: str) -> Response:
    """Download the dissent log as Markdown."""
    from council_core.export import render_markdown

    artifact = get_run_store().load(run_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    return PlainTextResponse(
        render_markdown(artifact),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="dissent-{run_id}.md"'},
    )


@router.get("/runs/{run_id}/export.html")
async def export_html(run_id: str) -> Response:
    """Download the dissent log as print-ready HTML (open and print to PDF)."""
    from council_core.export import render_html

    artifact = get_run_store().load(run_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    return Response(
        render_html(artifact),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="dissent-{run_id}.html"'},
    )
