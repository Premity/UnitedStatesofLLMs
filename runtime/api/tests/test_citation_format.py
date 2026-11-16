"""Malformed citations go back to the model, not to the resolver as fabrications.

Before this, an attacker that cited a real treaty article in the wrong shape
had it scored `unresolved`, which the metrics count as fabrication. In one run
all eight of the full council's "fabrications" on Galić were this one shape,
taken verbatim below.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.roles.attacker import _AttackerResponse
from app.roles.presenter import _PresenterResponse
from council_core.models.citation import Citation, CitationType, malformed_citations

#: An evidentiary attacker's citation from a live run: AP I art. 51(2), a real
#: provision, emitted as a "case" with the locator stuffed into `instrument`.
REAL_MALFORMED = {
    "type": "case",
    "instrument": "ap_i/art.51(2)",
    "quoted_text": "Acts or threats of violence the primary purpose of which is to spread "
    "terror among the civilian population are prohibited.",
}
WELL_FORMED = {"type": "treaty", "instrument": "ap_i", "article": "51(2)"}


def _objection(citations: list[dict]) -> dict:
    return {
        "raised_by": "attacker_evidentiary",
        "target_argument_id": "arg_1",
        "ground": "The record does not establish it.",
        "reasoning": "-",
        "citations": citations,
    }


@pytest.mark.parametrize(
    ("citation", "problem"),
    [
        (REAL_MALFORMED, "Case citation requires both a case id and a paragraph"),
        ({"type": "treaty", "instrument": "ap_i"}, "missing an article"),
        ({"type": "customary", "instrument": "customary_ihl"}, "missing a rule number"),
        (
            {"type": "treaty", "instrument": "ap_i/art.51", "article": "51"},
            "instrument's id alone",
        ),
    ],
)
def test_a_malformed_citation_says_what_is_wrong(citation: dict, problem: str) -> None:
    assert problem in (Citation.model_validate(citation).format_problem() or "")


@pytest.mark.parametrize(
    "citation",
    [
        WELL_FORMED,
        {"type": "case", "instrument": "icty", "case_id": "icty_galic_tj", "paragraph": "58"},
        {"type": "customary", "instrument": "customary_ihl", "rule_number": 2},
    ],
)
def test_a_well_formed_citation_has_no_problem(citation: dict) -> None:
    assert Citation.model_validate(citation).format_problem() is None


def test_an_attacker_reply_with_a_malformed_citation_is_rejected_with_the_reason() -> None:
    with pytest.raises(ValidationError) as raised:
        _AttackerResponse.model_validate(
            {"objections": [_objection([WELL_FORMED]), _objection([REAL_MALFORMED])]}
        )
    message = str(raised.value)
    assert "objections[1].citations[0]" in message
    assert '"type": "treaty"' in message  # the repair prompt shows the right shape


def test_a_well_formed_attacker_reply_parses() -> None:
    reply = _AttackerResponse.model_validate({"objections": [_objection([WELL_FORMED])]})
    assert reply.objections[0].citations[0].type is CitationType.TREATY


def test_a_presenter_reply_with_a_malformed_citation_is_rejected() -> None:
    argument = {
        "claim": "c",
        "reasoning": "r",
        "citations": [{"type": "treaty", "instrument": "ap_i"}],
    }
    with pytest.raises(ValidationError, match=r"arguments\[0\]\.citations\[0\]"):
        _PresenterResponse.model_validate({"arguments": [argument]})


def test_the_message_lists_every_problem_at_once() -> None:
    bad = Citation.model_validate(REAL_MALFORMED)
    message = malformed_citations([("objections[0]", [bad, bad])]) or ""
    assert message.count("Case citation requires") == 2
