"""Exercise each debate role on its own, one stage at a time. Development aid.

Stages save their output to data/scratch/, so a later stage can be re-run
without calling the models for the earlier ones again:

    uv run python scripts/try_roles.py presenter
    uv run python scripts/try_roles.py doctrinal
    uv run python scripts/try_roles.py evidentiary
    uv run python scripts/try_roles.py judge
"""

import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter
from run_debate import FACTS, QUESTION  # same test case as the full debate

from app.roles.attacker import AttackerRole
from app.roles.judge import JudgeRole
from app.roles.presenter import PresenterRole
from council_core.models.debate import (
    Argument,
    DebateConfig,
    Objection,
    ObjectionDisposition,
    Role,
)

SCRATCH = Path(os.environ.get("DATA_DIR", "data")) / "scratch"
ARGS_FILE = SCRATCH / "try_roles_arguments.json"
ARGS = TypeAdapter(list[Argument])
OBJS = TypeAdapter(list[Objection])

CONFIG = DebateConfig(
    question=QUESTION,
    facts=FACTS,
    rounds=1,
    max_rounds=1,
    enabled_attackers=[Role.ATTACKER_DOCTRINAL, Role.ATTACKER_EVIDENTIARY],
    retrieval_enabled=False,
)
ATTACKERS = {"doctrinal": Role.ATTACKER_DOCTRINAL, "evidentiary": Role.ATTACKER_EVIDENTIARY}


def objections_file(name: str) -> Path:
    return SCRATCH / f"try_roles_objections_{name}.json"


def citation_summary(items) -> str:
    counts = Counter(rc.status.value for item in items for rc in item.resolved_citations)
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no citations"


def check(ok: bool, label: str) -> bool:
    print(f"  {'OK  ' if ok else 'FAIL'} {label}")
    return ok


async def presenter() -> None:
    turn = await PresenterRole().run(
        config=CONFIG, context=[], prior_arguments=[], prior_objections=[], round_number=1
    )
    args = turn.arguments
    print(f"presenter  model={turn.model_id}  arguments={len(args)}")
    for a in args:
        print(f"  - {a.id}: {len(a.resolved_citations)} citation(s)")
    check(len(args) > 0, "returned at least one argument")
    check(all(a.resolved_citations for a in args), "every argument has citations")
    print(f"  citations: {citation_summary(args)}")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ARGS_FILE.write_bytes(ARGS.dump_json(args, indent=2))
    print(f"  saved -> {ARGS_FILE}")


async def attacker(name: str) -> None:
    args = load_arguments()
    try:
        turn = await AttackerRole(ATTACKERS[name]).run(
            config=CONFIG, context=[], arguments=args, round_number=1
        )
    except Exception as exc:
        print(f"{name}  FAIL  {type(exc).__name__}: {exc}")
        print("  A StructuredOutputError here is a finding: record the model in ISSUES.md.")
        raise SystemExit(1) from exc
    objs = turn.objections
    print(f"{name}  model={turn.model_id}  objections={len(objs)}")
    check(True, "returned valid structured output")
    check(len(objs) > 0, "raised at least one objection")
    print(f"  citations: {citation_summary(objs)}")
    objections_file(name).write_bytes(OBJS.dump_json(objs, indent=2))
    print(f"  saved -> {objections_file(name)}")


async def judge() -> None:
    args = load_arguments()
    objs: list[Objection] = []
    for name in ATTACKERS:
        f = objections_file(name)
        if f.exists():
            objs += OBJS.validate_json(f.read_bytes())
        else:
            print(f"  (no saved objections from {name}; run that stage first to include them)")
    turn, verdict, novel = await JudgeRole().run(
        config=CONFIG, context=[], arguments=args, objections=objs, round_number=1
    )
    print(f"judge  model={turn.model_id}  objections_in={len(objs)}  novel={novel}")
    unruled = [o.id for o in objs if o.disposition == ObjectionDisposition.UNADDRESSED]
    check(not unruled, f"ruled on every objection{'' if not unruled else f' (missed: {unruled})'}")
    check(0.0 <= verdict.confidence <= 1.0, f"confidence in [0, 1]: {verdict.confidence}")
    print(f"  dispositions: {dict(Counter(o.disposition.value for o in objs))}")


def load_arguments() -> list[Argument]:
    if not ARGS_FILE.exists():
        raise SystemExit(
            "No saved presenter output. Run: uv run python scripts/try_roles.py presenter"
        )
    return ARGS.validate_json(ARGS_FILE.read_bytes())


STAGES = {
    "presenter": presenter,
    "doctrinal": lambda: attacker("doctrinal"),
    "evidentiary": lambda: attacker("evidentiary"),
    "judge": judge,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        raise SystemExit(f"usage: try_roles.py {{{'|'.join(STAGES)}}}")
    asyncio.run(STAGES[sys.argv[1]]())
