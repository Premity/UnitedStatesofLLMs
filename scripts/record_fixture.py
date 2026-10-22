"""Record one debate's SSE event sequence as the frontend replay fixture (T0-5).

Drives the real `/debate/stream` handler in-process, so the events are exactly
what the frontend receives, and the run is persisted to data/runs/ as usual.
No server needed:

    uv run --env-file .env python scripts/record_fixture.py

Writes runtime/frontend/src/fixtures/sample-run.json as a list of
{"event": name, "data": payload}. Payloads are parsed from the JSON strings the
stream carries, so a replay server must re-serialise them.
"""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from run_debate import FACTS, QUESTION  # same test case as the driver

from app.routers.debate import stream_debate
from council_core.models.debate import DebateConfig, Role

OUT = Path(__file__).resolve().parents[1] / "runtime/frontend/src/fixtures/sample-run.json"


async def main(args: argparse.Namespace) -> None:
    config = DebateConfig(
        question=QUESTION,
        facts=FACTS,
        rounds=args.rounds,
        max_rounds=args.rounds,
        enabled_attackers=[Role.ATTACKER_DOCTRINAL, Role.ATTACKER_EVIDENTIARY],
        retrieval_enabled=True,
    )
    response = await stream_debate(config)

    events = []
    async for frame in response.body_iterator:
        events.append({"event": frame["event"], "data": json.loads(frame["data"])})
        print(f"  {frame['event']}")

    names = [e["event"] for e in events]
    turns = [e["data"] for e in events if e["event"] == "turn"]
    objections = [o for t in turns for o in t.get("objections", [])]
    statuses = Counter(
        rc["status"]
        for t in turns
        for item in t.get("arguments", []) + t.get("objections", [])
        for rc in item.get("resolved_citations", [])
    )

    print(f"\nsequence:   {' -> '.join(dict.fromkeys(names))}")
    print(f"objections: {len(objections)}")
    print(f"citations:  {dict(statuses) or 'none'}")

    problems = []
    if names[:1] != ["start"] or names[-1:] != ["done"]:
        problems.append("sequence does not run start ... done")
    if "verdict" not in names:
        problems.append("no verdict event (the run failed; see the error event)")
    if len(objections) < 2:
        problems.append("fewer than two objections; the dissent log will look empty")
    if not statuses.get("unresolved"):
        problems.append("no unresolved citation; re-run if you want one for the UI (optional)")

    if problems and not args.force and any("verdict" in p or "sequence" in p for p in problems):
        print("\nNot written:\n  - " + "\n  - ".join(problems))
        raise SystemExit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT}")
    for p in problems:
        print(f"  note: {p}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--force", action="store_true", help="write even if the run failed")
    asyncio.run(main(p.parse_args()))
