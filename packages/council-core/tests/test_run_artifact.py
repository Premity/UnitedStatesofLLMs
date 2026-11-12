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
from pydantic import ValidationError

from council_core.models.debate import (
    DebateConfig,
    DebateState,
    Objection,
    ObjectionSeverity,
    Role,
)
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


def test_an_objection_recorded_before_severity_existed_still_loads() -> None:
    """The field is additive, and stored runs are permanent.

    Every run artifact ever written lacks `severity`. If adding it made those
    files unreadable, the past runs would be lost -- so a missing value must
    validate, and must mean "not stated" rather than any particular rating.
    """
    stored = {
        "id": "obj_legacy01",
        "raised_by": "attacker_doctrinal",
        "target_argument_id": "arg_abc12345",
        "ground": "The Protocol does not apply.",
        "reasoning": "Article 1 limits its field of application.",
        "citations": [],
        "resolved_citations": [],
        "disposition": "overruled",
        "disposition_reasoning": "The prohibition is customary.",
    }

    objection = Objection.model_validate(stored)

    assert objection.severity is None


def test_severity_round_trips_through_a_stored_artifact() -> None:
    """A rating written into a run artifact must survive being read back."""
    objection = Objection(
        target_argument_id="arg_abc12345",
        ground="The factual predicate is not established.",
        reasoning="No evidence of purpose is identified.",
        raised_by=Role.ATTACKER_EVIDENTIARY,
        severity=ObjectionSeverity.FATAL,
    )

    restored = Objection.model_validate_json(objection.model_dump_json())

    assert restored.severity is ObjectionSeverity.FATAL


def test_rejects_a_severity_outside_the_three_steps() -> None:
    """Three named steps, not a free-text field or a number.

    A model asked for a score invents precision it does not have, so the
    vocabulary is closed and anything else is a validation error the structured
    output repair can show the model.
    """
    with pytest.raises(ValidationError):
        Objection(
            target_argument_id="arg_abc12345",
            ground="g",
            reasoning="r",
            severity="catastrophic",  # type: ignore[arg-type]
        )
