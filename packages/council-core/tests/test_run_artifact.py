"""Tests for `RunArtifact.from_json`'s load-time `raised_by` check.

`Objection.raised_by` defaults to `attacker_doctrinal` so a *live* model
response can omit the field during parsing -- `AttackerRole.run()` always
overwrites it with the true role before anything is saved. A *stored*
artifact missing the field should never silently fall into that same
default, because `independence.measure_independence` counts objections by
`raised_by` to score how differently the two attackers behave (GitHub
#11-5): a mislabelled objection would skew that metric without ever raising
an error.
"""

from __future__ import annotations

import json

import pytest

from council_core.models.debate import DebateConfig, DebateState, Objection, Role
from council_core.models.run import RunArtifact, RunMetadata


def _build_artifact() -> RunArtifact:
    objection = Objection(
        raised_by=Role.ATTACKER_EVIDENTIARY,
        target_argument_id="arg_00000000",
        ground="The facts do not establish this.",
        reasoning="No evidence in the record supports the claim.",
    )
    state = DebateState(
        config=DebateConfig(question="Did the attack violate the principle of distinction?"),
        objections=[objection],
    )
    return RunArtifact(metadata=RunMetadata(run_id="run_test"), state=state)


def test_round_trips_a_valid_artifact() -> None:
    artifact = _build_artifact()
    loaded = RunArtifact.from_json(artifact.to_json())
    assert loaded.state.objections[0].raised_by == Role.ATTACKER_EVIDENTIARY


def test_rejects_a_stored_objection_with_no_explicit_raised_by() -> None:
    raw = json.loads(_build_artifact().to_json())
    del raw["state"]["objections"][0]["raised_by"]

    with pytest.raises(ValueError, match="raised_by"):
        RunArtifact.from_json(json.dumps(raw))
