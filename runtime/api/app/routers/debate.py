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
from council_core.models.debate import DebateConfig, DebateState
from council_core.models.run import RunArtifact, RunMetadata, RunStatus

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/debate", tags=["debate"])

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
        `turn`       one role finished — carries the full Turn object
        `verdict`    the judge ruled
        `done`       the run finished — carries run_id and the final state
        `error`      the run failed
    """
    state = DebateState(config=config)
    metadata = _initial_metadata(state.run_id)
    store = get_run_store()

    async def events() -> AsyncIterator[dict[str, str]]:
        started = datetime.now(UTC)
        seen_turns = 0

        yield {"event": "start", "data": json.dumps({"run_id": state.run_id})}

        async with _get_semaphore():
            try:
                async for chunk in compiled_graph.astream(
                    {"run_id": state.run_id, "config": config, "current_round": 0},
                    stream_mode="values",
                ):
                    turns = chunk.get("turns", [])

                    # Emit only turns the client has not seen yet.
                    for turn in turns[seen_turns:]:
                        yield {
                            "event": "turn",
                            "data": turn.model_dump_json(),
                        }
                    seen_turns = len(turns)

                    if (verdict := chunk.get("verdict")) is not None:
                        yield {"event": "verdict", "data": verdict.model_dump_json()}

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

    return EventSourceResponse(events())


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
