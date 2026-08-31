"""Tests for the dissent log renderer.

The export is the deliverable a human reads, so the things tested here are the
things that would mislead that reader.
"""

from __future__ import annotations

from council_core.export import render_markdown
from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)
from council_core.models.debate import (
    Argument,
    DebateConfig,
    DebateState,
    Objection,
    ObjectionDisposition,
    Role,
    Verdict,
)
from council_core.models.run import RunArtifact, RunMetadata, RunStatus


def build_artifact() -> RunArtifact:
    argument = Argument(
        id="arg_1",
        claim="The attack was disproportionate.",
        reasoning="Incidental harm exceeded the anticipated military advantage.",
        resolved_citations=[
            ResolvedCitation(
                citation=Citation(
                    type=CitationType.TREATY, instrument="rome_statute", article="8(2)(b)(iv)"
                ),
                status=CitationStatus.RESOLVED,
                corpus_text="Intentionally launching an attack…",
            )
        ],
    )

    overruled = Objection(
        id="obj_1",
        raised_by=Role.ATTACKER_DOCTRINAL,
        target_argument_id="arg_1",
        ground="Proportionality is assessed ex ante, not with hindsight.",
        reasoning="The commander's information at the time is the correct frame.",
        disposition=ObjectionDisposition.OVERRULED,
        disposition_reasoning="The record shows the commander had the relevant information.",
    )

    fabricated = Objection(
        id="obj_2",
        raised_by=Role.ATTACKER_EVIDENTIARY,
        target_argument_id="arg_1",
        ground="The evidence does not establish the casualty figures.",
        reasoning="Reported figures come from a single source.",
        resolved_citations=[
            ResolvedCitation(
                citation=Citation(
                    type=CitationType.CASE,
                    instrument="icty",
                    case_id="icty_nonexistent_tj",
                    paragraph="999",
                ),
                status=CitationStatus.UNRESOLVED,
                note="No span at this locator.",
            )
        ],
        disposition=ObjectionDisposition.OVERRULED,
        disposition_reasoning="Rests on authority that does not resolve.",
    )

    state = DebateState(
        run_id="run_test",
        config=DebateConfig(question="Was the attack disproportionate?", facts="Facts."),
        current_round=2,
        arguments=[argument],
        objections=[overruled, fabricated],
        terminated_reason="no_novel_objections",
        verdict=Verdict(
            conclusion="The attack was disproportionate.",
            reasoning="The surviving arguments support the conclusion.",
            confidence=0.62,
            confidence_reasoning="The proportionality assessment is genuinely contested.",
            surviving_argument_ids=["arg_1"],
            dissent=[overruled, fabricated],
        ),
    )

    return RunArtifact(
        metadata=RunMetadata(
            run_id="run_test",
            status=RunStatus.COMPLETED,
            role_models={"presenter": "mistral/magistral-medium-latest"},
        ),
        state=state,
    )


def test_dissent_log_includes_every_overruled_objection() -> None:
    md = render_markdown(build_artifact())
    assert "Proportionality is assessed ex ante" in md
    assert "The evidence does not establish the casualty figures" in md


def test_dissent_log_states_why_each_objection_was_overruled() -> None:
    """A dissent entry without a reason tells a reviewer nothing."""
    md = render_markdown(build_artifact())
    assert "Overruled because" in md
    assert "the commander had the relevant information" in md.lower()


def test_unresolved_citations_are_marked_not_hidden() -> None:
    """A reader must be able to see where a model reached for authority that does not exist."""
    md = render_markdown(build_artifact())
    assert "UNRESOLVED" in md
    assert "icty_nonexistent_tj/para.999" in md


def test_confidence_is_reported_with_its_justification() -> None:
    md = render_markdown(build_artifact())
    assert "62%" in md
    assert "genuinely contested" in md


def test_an_incomplete_run_renders_without_a_verdict() -> None:
    artifact = build_artifact()
    artifact.state.verdict = None
    artifact.metadata.status = RunStatus.FAILED
    artifact.metadata.error = "Judge timed out."

    md = render_markdown(artifact)
    assert "did not complete" in md
    assert "Judge timed out." in md
