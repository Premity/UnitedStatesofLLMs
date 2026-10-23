"""The citation index is what makes citation validation work at all.

Each test here guards a failure that produces plausible numbers rather than an
error: a missing `instruments` list turns every coverage gap into a fabrication
signal, and a locator mismatch turns a correct citation into one.
"""

from __future__ import annotations

import json

import pytest
from indexer.index.citation_index import build_index, write_index

from council_core.citations.resolver import CitationResolver, JsonCorpusIndex
from council_core.models.citation import Citation, CitationStatus, CitationType
from council_core.models.corpus import CorpusDocument, DocumentType, Span

AP_I_51_2 = (
    "The civilian population as such, as well as individual civilians, shall not be "
    "the object of attack."
)


def ap_i() -> CorpusDocument:
    return CorpusDocument(
        id="ap_i",
        type=DocumentType.TREATY,
        title="Protocol Additional I",
        source_url="https://example.org/ap_i",
        spans=[
            Span(locator="ap_i/art.51", text="Article 51 in full.", article="51"),
            Span(locator="ap_i/art.51(2)", text=AP_I_51_2, article="51(2)", parent="ap_i/art.51"),
        ],
    )


def test_index_carries_both_entries_and_instruments() -> None:
    """`instruments` is what separates a coverage gap from a fabrication.

    Without it every miss resolves `unresolved`, and `fabrication_rate`
    measures nothing. Non-negotiable #2.
    """
    index = build_index([ap_i()])
    assert index["instruments"] == ["ap_i"]
    assert set(index["entries"]) == {"ap_i/art.51", "ap_i/art.51(2)"}


def test_two_documents_cannot_claim_one_locator() -> None:
    """Otherwise which text a locator resolves to depends on iteration order."""
    other = CorpusDocument(
        id="ap_i",
        type=DocumentType.TREATY,
        title="A second copy",
        source_url="https://example.org/dup",
        spans=[Span(locator="ap_i/art.51", text="Different text.", article="51")],
    )
    with pytest.raises(ValueError, match="more than one document"):
        build_index([ap_i(), other])


def test_entries_keep_the_text_verbatim() -> None:
    """A paraphrase makes a correct quotation resolve `misquoted`."""
    index = build_index([ap_i()])
    assert index["entries"]["ap_i/art.51(2)"]["text"] == AP_I_51_2


@pytest.mark.parametrize(
    ("expected", "citation"),
    [
        (
            CitationStatus.RESOLVED,
            Citation(type=CitationType.TREATY, instrument="ap_i", article="51(2)"),
        ),
        (
            CitationStatus.UNRESOLVED,
            Citation(type=CitationType.TREATY, instrument="ap_i", article="999"),
        ),
        (
            CitationStatus.OUT_OF_CORPUS,
            Citation(type=CitationType.TREATY, instrument="gc_i", article="3"),
        ),
        (
            CitationStatus.MISQUOTED,
            Citation(
                type=CitationType.TREATY,
                instrument="ap_i",
                article="51(2)",
                quoted_text="Cats are prohibited from wearing hats.",
            ),
        ),
    ],
)
def test_the_runtime_resolver_reads_what_we_write(
    tmp_path, expected: CitationStatus, citation: Citation
) -> None:
    """The real resolver, not a reimplementation of it.

    This is the contract between the offline pipeline and the runtime: if the
    index we emit does not produce all four statuses through
    `CitationResolver`, citation validation is broken however well-formed the
    file looks.
    """
    path = tmp_path / "citation_index.json"
    write_index([ap_i()], path)

    resolver = CitationResolver(JsonCorpusIndex(path))
    assert resolver.resolve(citation).status is expected


def test_write_is_atomic(tmp_path) -> None:
    """The runtime reads this path live. A half-written file would be read as a
    corpus that has lost most of its articles."""
    path = tmp_path / "citation_index.json"
    write_index([ap_i()], path)

    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads(path.read_text(encoding="utf-8"))["entries"]


def test_an_empty_corpus_produces_a_valid_but_empty_index() -> None:
    """Better an index that resolves everything `out_of_corpus` than a crash
    midway through `make index`, which leaves the old index in place."""
    index = build_index([])
    assert index["instruments"] == []
    assert index["entries"] == {}
