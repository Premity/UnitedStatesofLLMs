"""The settings a scored run is frozen to, and the check that a machine matches them.

The scored run (#26) may be split across several people's machines. Their
results can only be pooled if every one ran the same models, the same prompts,
the same embedding model and the same citation index (ADR 0009 freezes the
roster; ADR 0014 shares the index). Each of those differs silently between
machines: `.env` sets the roster, `prompts/` can have local edits, and the index
is a per-machine artifact.

    python -m harness.settings            # print this machine's settings and check them
    python -m harness.settings --freeze   # record them as the frozen settings

`evaluation/frozen-settings.json` is committed. Once it exists, a live run on a
machine whose settings differ refuses to start, naming every difference.

API keys are never read or printed: only model ids, hashes and counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FROZEN_PATH = Path(__file__).resolve().parents[1] / "frozen-settings.json"

#: The roles whose model ids make up the roster, in debate order.
ROSTER_ROLES = ("presenter", "attacker_doctrinal", "attacker_evidentiary", "judge")

#: The keys compared between machines. `recorded_at` and `fingerprint` are not.
COMPARED = ("roster", "prompts", "embedding_model", "corpus")


class SettingsMismatchError(RuntimeError):
    """This machine's settings differ from the frozen ones."""


def fingerprint(settings: Mapping[str, Any]) -> str:
    """A short hash of exactly the compared settings, for comparing by eye."""
    canonical = json.dumps({k: settings.get(k) for k in COMPARED}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def current_settings() -> dict[str, Any]:
    """What this machine would run with, read the way a live run reads it."""
    # harness.run must be imported first: it points DATA_DIR, PROMPTS_DIR and
    # QDRANT_URL at the host's paths, and the app's settings read them once.
    import harness.run as run_module

    prompts = run_module.composite_prompt_hash(run_module.compute_prompt_hashes())

    from app.core.config import get_role_models, get_settings
    from app.roles.base import get_resolver

    models = get_role_models()
    identity = get_resolver().corpus_identity()
    settings: dict[str, Any] = {
        "roster": {role: models.for_role(role).model_id for role in ROSTER_ROLES},
        "prompts": prompts,
        "embedding_model": get_settings().embedding_model,
        "corpus": identity.content_hash if identity else None,
    }
    settings["fingerprint"] = fingerprint(settings)
    return settings


def load_frozen(path: Path | None = None) -> dict[str, Any] | None:
    # Looked up at call time, not bound as a default, so tests can point it elsewhere.
    path = path or FROZEN_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def differences(current: Mapping[str, Any], frozen: Mapping[str, Any]) -> list[str]:
    """Every compared setting that differs, as a sentence naming both values."""
    found = []
    for role in ROSTER_ROLES:
        here = current.get("roster", {}).get(role)
        there = frozen.get("roster", {}).get(role)
        if here != there:
            found.append(f"{role} model is {here!r} here, frozen as {there!r} (.env)")
    if current.get("prompts") != frozen.get("prompts"):
        found.append(
            f"prompt set is {str(current.get('prompts'))[:12]} here, frozen as "
            f"{str(frozen.get('prompts'))[:12]} (a local edit under prompts/, or the wrong branch)"
        )
    if current.get("embedding_model") != frozen.get("embedding_model"):
        found.append(
            f"EMBEDDING_MODEL is {current.get('embedding_model')!r} here, frozen as "
            f"{frozen.get('embedding_model')!r}"
        )
    if current.get("corpus") != frozen.get("corpus"):
        found.append(
            f"citation index is {str(current.get('corpus'))[:12]} here, frozen as "
            f"{str(frozen.get('corpus'))[:12]} (import the shared index bundle; ADR 0014)"
        )
    return found


def require_frozen_settings(
    current: Mapping[str, Any] | None = None, *, path: Path | None = None
) -> None:
    """Refuse a live run whose settings differ from the frozen ones, if any are frozen."""
    path = path or FROZEN_PATH
    frozen = load_frozen(path)
    if frozen is None:
        return
    found = differences(current if current is not None else current_settings(), frozen)
    if found:
        raise SettingsMismatchError(
            "This machine's settings differ from the frozen ones in "
            f"{path.name}, so its results could not be pooled with the others:\n- "
            + "\n- ".join(found)
            + "\nFix the machine (see docs/runbook-evaluation.md), or pass "
            "--allow-unfrozen-settings for a deliberate experiment that will not be scored."
        )


def describe(settings: Mapping[str, Any]) -> list[str]:
    lines = [f"  {role:21} {settings['roster'][role]}" for role in ROSTER_ROLES]
    lines += [
        f"  {'prompt set':21} {str(settings['prompts'])[:12]}",
        f"  {'embedding model':21} {settings['embedding_model']}",
        f"  {'citation index':21} {str(settings['corpus'])[:12]}",
        f"  {'fingerprint':21} {settings['fingerprint']}",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--freeze",
        action="store_true",
        help=f"Record this machine's settings as the frozen ones ({FROZEN_PATH.name}).",
    )
    args = parser.parse_args(argv)

    current = current_settings()
    print("This machine's evaluation settings:")
    print("\n".join(describe(current)))

    if args.freeze:
        FROZEN_PATH.write_text(
            json.dumps({**current, "recorded_at": datetime.now(UTC).isoformat()}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nFrozen to {FROZEN_PATH}. Commit it so every machine checks against it.")
        return 0

    frozen = load_frozen()
    if frozen is None:
        print("\nNothing is frozen yet: no evaluation/frozen-settings.json.")
        return 0
    found = differences(current, frozen)
    if found:
        print("\nDIFFERS from the frozen settings:\n- " + "\n- ".join(found), file=sys.stderr)
        return 1
    print(f"\nMatches the frozen settings (recorded {frozen.get('recorded_at', '?')[:10]}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
