"""A retrieved span must carry the locator the citation index knows.

The context every role reads renders each span as `[<locator>]` and says these
are the only sources to cite. A wrong locator there invites a citation that
resolves `unresolved`, which the metrics count as fabrication.
"""

from __future__ import annotations

import pytest

from app.services.retrieval import _citation_from_payload


@pytest.mark.parametrize(
    "payload",
    [
        {
            "locator": "ap_i/art.51(2)",
            "citation_type": "treaty",
            "instrument": "ap_i",
            "article": "51(2)",
        },
        {
            "locator": "icty_galic_tj/para.58",
            "citation_type": "case",
            "instrument": "icty_galic_tj",
            "case_id": "icty_galic_tj",
            "paragraph": "58",
        },
        {
            "locator": "customary_ihl/rule.2",
            "citation_type": "customary",
            "instrument": "customary_ihl",
            "rule_number": 2,
        },
    ],
)
def test_a_payload_rebuilds_its_stored_locator(payload: dict) -> None:
    assert _citation_from_payload(payload).locator() == payload["locator"]


def test_a_rule_indexed_without_its_number_takes_it_from_the_locator() -> None:
    """Every collection built before the indexer fix stores `rule_number: null`,
    including shared index bundles; they must not need re-embedding."""
    payload = {
        "locator": "customary_ihl/rule.24",
        "citation_type": "customary",
        "instrument": "customary_ihl",
        "rule_number": None,
    }
    assert _citation_from_payload(payload).locator() == "customary_ihl/rule.24"
