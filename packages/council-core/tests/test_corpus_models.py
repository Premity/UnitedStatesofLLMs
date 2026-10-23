"""The corpus document contract.

These tests exist because every failure they describe is silent. A span filed
under a malformed locator is indexed successfully, retrieved never, and shows
up in the metrics as the model citing something that does not exist.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from council_core.models.citation import Citation, CitationType
from council_core.models.corpus import CorpusDocument, DocumentType, Span


def treaty(**kwargs) -> CorpusDocument:
    return CorpusDocument(
        id=kwargs.pop("id", "ap_i"),
        type=DocumentType.TREATY,
        title=kwargs.pop("title", "Protocol Additional I"),
        source_url=kwargs.pop("source_url", "https://example.org/ap_i"),
        **kwargs,
    )


@pytest.mark.parametrize("article", ["51", "51(2)", "8(2)(b)(iv)", "23(g)"])
def test_span_locators_match_what_a_model_will_cite(article: str) -> None:
    """A span's locator must be byte-identical to `Citation.locator()`.

    This is the join between the corpus and the resolver. If the indexer writes
    `ap_i/art.51.2` and a model cites `ap_i/art.51(2)`, the lookup misses and a
    correct citation is scored as a fabrication.
    """
    span = Span(locator=f"ap_i/art.{article}", text="…", article=article)
    citation = Citation(type=CitationType.TREATY, instrument="ap_i", article=article)
    assert span.locator == citation.locator()


@pytest.mark.parametrize(
    "locator",
    [
        "ap_i/art.51.2",  # sub-paragraph with a dot
        "ap_i/art.51/para.2",  # sub-paragraph as a path segment
        "AP_I/art.51",  # uppercase instrument
        "ap_i/51",  # no art. prefix
        "ap_i/article.51",  # spelled out
        "ap_i/art.",  # no article
        "ap_i/art.51(2",  # unbalanced
    ],
)
def test_malformed_locators_are_rejected(locator: str) -> None:
    """ADR 0008 fixes one spelling per provision.

    Two spellings in the index means half the citations to that provision miss.
    """
    with pytest.raises(ValidationError):
        Span(locator=locator, text="…")


def test_a_span_cannot_be_filed_under_another_document() -> None:
    """A misfiled span is indexed under a locator nobody will cite."""
    with pytest.raises(ValidationError, match="does not belong"):
        treaty(spans=[Span(locator="gc_iv/art.27", text="…")])


def test_duplicate_locators_are_rejected() -> None:
    """Two spans on one locator means one silently wins at lookup."""
    with pytest.raises(ValidationError, match="Duplicate"):
        treaty(
            spans=[
                Span(locator="ap_i/art.51", text="first"),
                Span(locator="ap_i/art.51", text="second"),
            ]
        )


def test_a_treaty_cannot_hold_paragraph_locators() -> None:
    """Treaties are cited by article, judgments by paragraph.

    Mixing them produces a locator no model will emit, so the provision is
    present in the index and unreachable from a citation.
    """
    with pytest.raises(ValidationError, match="wrong locator form"):
        treaty(spans=[Span(locator="ap_i/para.51", text="…")])


def test_a_judgment_cannot_hold_article_locators() -> None:
    with pytest.raises(ValidationError, match="wrong locator form"):
        CorpusDocument(
            id="icty_galic_tj",
            type=DocumentType.CASE,
            title="Prosecutor v. Galić",
            source_url="https://example.org/galic",
            court="ICTY",
            spans=[Span(locator="icty_galic_tj/art.58", text="…")],
        )


def test_empty_span_text_is_rejected() -> None:
    """An empty span makes every quotation against it resolve `misquoted`."""
    with pytest.raises(ValidationError, match="empty"):
        Span(locator="ap_i/art.51", text="   ")


def test_corpus_ids_are_slugs() -> None:
    """Ids are written into every stored run artifact, so they are permanent."""
    with pytest.raises(ValidationError, match="snake_case"):
        treaty(id="AP-I")


def test_a_whole_article_and_its_paragraph_are_distinct_spans() -> None:
    """ADR 0008: `art.51` does not resolve `art.51(2)`, or the reverse.

    They carry different text, and a quotation is checked against whichever one
    the locator resolves to.
    """
    doc = treaty(
        spans=[
            Span(locator="ap_i/art.51", text="Article 51 in full…", article="51"),
            Span(
                locator="ap_i/art.51(2)",
                text="The civilian population as such…",
                article="51(2)",
                parent="ap_i/art.51",
            ),
        ]
    )
    assert doc.locators() == ["ap_i/art.51", "ap_i/art.51(2)"]


def test_parent_gives_a_short_span_context_without_merging_it() -> None:
    """Some articles are one line. The parent link is how the embedder gets
    context without collapsing two citable units into one chunk."""
    span = Span(locator="ap_i/art.51(2)", text="…", article="51(2)", parent="ap_i/art.51")
    assert span.parent == "ap_i/art.51"
