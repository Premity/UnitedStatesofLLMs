"""Drive one debate from the command line and persist it. Development aid, not a product."""

import argparse
import asyncio
from datetime import UTC, datetime

from app.graph.workflow import compiled_graph
from app.routers.debate import _initial_metadata
from app.services.run_store import get_run_store
from council_core.models.debate import DebateConfig, DebateState, Role
from council_core.models.run import RunArtifact, RunStatus

QUESTION = (
    "Does a sustained campaign of sniping and shelling directed at civilians, conducted "
    "with the primary purpose of spreading terror, violate the laws or customs of war?"
)
FACTS = (
    "Over roughly 23 months, forces under the accused's command conducted sniping and "
    "shelling against civilian areas of a besieged city..."
)
ATTACKERS = {"doctrinal": Role.ATTACKER_DOCTRINAL, "evidentiary": Role.ATTACKER_EVIDENTIARY}


async def main(args: argparse.Namespace) -> None:
    rounds = args.rounds if args.rounds == "auto" else int(args.rounds)
    config = DebateConfig(
        question=QUESTION,
        facts=FACTS,
        rounds=rounds,
        max_rounds=args.max_rounds,
        enabled_attackers=[ATTACKERS[a] for a in args.attackers],
        retrieval_enabled=args.retrieval,
    )
    state = DebateState(config=config)
    metadata = _initial_metadata(state.run_id)
    started = datetime.now(UTC)
    seen = 0

    try:
        async for chunk in compiled_graph.astream(
            {"run_id": state.run_id, "config": config, "current_round": 0},
            stream_mode="values",
        ):
            turns = chunk.get("turns", [])
            for turn in turns[seen:]:
                print(f"round {turn.round_number} {turn.role.value:22} {turn.model_id}")
            seen = len(turns)
            state.turns = turns
            state.arguments = chunk.get("arguments", [])
            state.objections = chunk.get("objections", [])
            state.context = chunk.get("context", [])
            state.current_round = chunk.get("current_round", 0)
            state.verdict = chunk.get("verdict")
            state.terminated_reason = chunk.get("terminated_reason")
        metadata.status = RunStatus.COMPLETED
    except Exception as exc:
        metadata.status = RunStatus.FAILED
        metadata.error = str(exc)
        raise
    finally:
        metadata.completed_at = datetime.now(UTC)
        metadata.duration_seconds = (metadata.completed_at - started).total_seconds()
        path = get_run_store().save(RunArtifact(metadata=metadata, state=state))
        print(f"\nstatus={metadata.status.value} saved to {path}")
        if state.verdict:
            print(f"confidence={state.verdict.confidence} objections={len(state.objections)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", default="1")
    p.add_argument("--max-rounds", type=int, default=1)
    p.add_argument("--attackers", nargs="*", default=[], choices=list(ATTACKERS))
    p.add_argument("--retrieval", action="store_true")
    asyncio.run(main(p.parse_args()))
