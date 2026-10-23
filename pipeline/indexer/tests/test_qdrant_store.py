"""The Qdrant payload is a contract with the API.

`RetrievalService` rebuilds a `Citation` from these exact field names, so a
rename here returns spans the resolver cannot match -- with no error.
"""

from __future__ import annotations

import pytest
from indexer.index.qdrant_store import point_id, span_payload

from council_core.models.citation import Citation, CitationType
from council_core.models.corpus import CorpusDocument, DocumentType, Span


def treaty_doc() -> CorpusDocument:
    return CorpusDocument(
        id="ap_i",
        type=DocumentType.TREATY,
        title="Protocol Additional I",
        source_url="https://example.org/ap_i",
        spans=[
            Span(locator="ap_i/art.51", text="Article 51 in full.", article="51"),
            Span(
                locator="ap_i/art.51(2)",
                text="The civilian population as such…",
                article="51(2)",
                parent="ap_i/art.51",
            ),
        ],
    )


def case_doc() -> CorpusDocument:
    return CorpusDocument(
        id="icty_galic_tj",
        type=DocumentType.CASE,
        title="Prosecutor v. Galić",
        source_url="https://example.org/galic",
        court="ICTY",
        spans=[Span(locator="icty_galic_tj/para.58", text="The Chamber finds…", paragraph="58")],
    )


def test_payload_rebuilds_the_citation_the_api_expects() -> None:
    """The round trip the API performs on every retrieved span."""
    doc = treaty_doc()
    payload = span_payload(doc, doc.spans[1])

    citation = Citation(
        type=CitationType(payload["citation_type"]),
        instrument=payload["instrument"],
        article=payload["article"],
        case_id=payload["case_id"],
        paragraph=payload["paragraph"],
        rule_number=payload["rule_number"],
    )
    assert citation.locator() == "ap_i/art.51(2)"


def test_a_case_payload_rebuilds_a_paragraph_locator() -> None:
    doc = case_doc()
    payload = span_payload(doc, doc.spans[0])

    citation = Citation(
        type=CitationType(payload["citation_type"]),
        instrument=payload["instrument"],
        case_id=payload["case_id"],
        paragraph=payload["paragraph"],
    )
    assert citation.locator() == "icty_galic_tj/para.58"


def test_payload_carries_the_text_verbatim() -> None:
    """The judge checks a quotation against this, so it is the provision as
    published, not the embedding input."""
    doc = treaty_doc()
    assert span_payload(doc, doc.spans[1])["text"] == "The civilian population as such…"


def test_payload_keeps_the_locator_for_the_join() -> None:
    doc = treaty_doc()
    assert span_payload(doc, doc.spans[1])["locator"] == "ap_i/art.51(2)"


def test_point_ids_are_derived_from_the_locator() -> None:
    """Re-indexing must overwrite, not accumulate: duplicate points would
    split retrieval between a stale copy and a fresh one."""
    assert point_id("ap_i/art.51(2)") == point_id("ap_i/art.51(2)")
    assert point_id("ap_i/art.51") != point_id("ap_i/art.51(2)")


@pytest.mark.parametrize(
    "field",
    [
        "locator",
        "citation_type",
        "instrument",
        "article",
        "case_id",
        "paragraph",
        "rule_number",
        "text",
        "source_url",
    ],
)
def test_every_field_the_api_reads_is_present(field: str) -> None:
    doc = treaty_doc()
    assert field in span_payload(doc, doc.spans[0])
