"""Tests for the citation resolver — the anti-fabrication machinery.

These are the tests that matter most in this repo: if the resolver silently
accepts a made-up citation, the project's central claim is false.
"""

from __future__ import annotations

import pytest

from council_core.citations import CitationResolver
from council_core.models.citation import Citation, CitationStatus, CitationType


class FakeIndex:
    """In-memory `CorpusIndex` for testing without Qdrant."""

    def __init__(self, entries: dict[str, str], instruments: set[str]) -> None:
        self._entries = entries
        self._instruments = instruments

    def lookup(self, locator: str) -> tuple[str, str | None] | None:
        text = self._entries.get(locator)
        return (text, None) if text is not None else None

    def knows_instrument(self, instrument: str) -> bool:
        return instrument in self._instruments


@pytest.fixture
def resolver() -> CitationResolver:
    return CitationResolver(
        FakeIndex(
            entries={
                "rome_statute/art.8(2)(b)(iv)": (
                    "Intentionally launching an attack in the knowledge that such "
                    "attack will cause incidental loss of life or injury to civilians"
                ),
                "icty_galic_tj/para.58": "The Trial Chamber finds that the attacks were sustained.",
            },
            instruments={"rome_statute", "icty_galic_tj", "gc_iv"},
        )
    )


def test_resolves_a_real_treaty_citation(resolver: CitationResolver) -> None:
    result = resolver.resolve(
        Citation(type=CitationType.TREATY, instrument="rome_statute", article="8(2)(b)(iv)")
    )
    assert result.status == CitationStatus.RESOLVED
    assert result.is_supported
    assert "incidental loss of life" in (result.corpus_text or "")


def test_flags_a_fabricated_article_in_a_known_instrument(resolver: CitationResolver) -> None:
    """The core fabrication case: real treaty, invented subparagraph."""
    result = resolver.resolve(
        Citation(type=CitationType.TREATY, instrument="rome_statute", article="8(2)(z)(99)")
    )
    assert result.status == CitationStatus.UNRESOLVED
    assert not result.is_supported


def test_distinguishes_out_of_corpus_from_fabricated(resolver: CitationResolver) -> None:
    """An unindexed instrument is unverifiable, not evidence of fabrication.

    Conflating these would make the fabrication rate meaningless.
    """
    result = resolver.resolve(
        Citation(type=CitationType.TREATY, instrument="some_unindexed_treaty", article="5")
    )
    assert result.status == CitationStatus.OUT_OF_CORPUS
    assert not result.is_supported


def test_flags_a_fabricated_case_paragraph(resolver: CitationResolver) -> None:
    result = resolver.resolve(
        Citation(
            type=CitationType.CASE,
            instrument="icty_galic_tj",
            case_id="icty_galic_tj",
            paragraph="99999",
        )
    )
    assert result.status == CitationStatus.UNRESOLVED


def test_rejects_a_treaty_citation_with_no_article(resolver: CitationResolver) -> None:
    result = resolver.resolve(Citation(type=CitationType.TREATY, instrument="rome_statute"))
    assert result.status == CitationStatus.UNRESOLVED
    assert "article" in (result.note or "").lower()


def test_rejects_a_case_citation_with_no_paragraph(resolver: CitationResolver) -> None:
    result = resolver.resolve(
        Citation(type=CitationType.CASE, instrument="icty", case_id="icty_galic_tj")
    )
    assert result.status == CitationStatus.UNRESOLVED


def test_detects_a_quotation_that_is_not_in_the_source(resolver: CitationResolver) -> None:
    result = resolver.resolve(
        Citation(
            type=CitationType.TREATY,
            instrument="rome_statute",
            article="8(2)(b)(iv)",
            quoted_text="the accused shall be presumed guilty until proven otherwise",
        )
    )
    assert result.status == CitationStatus.MISQUOTED


def test_accepts_a_loosely_worded_but_genuine_quotation(resolver: CitationResolver) -> None:
    """Models normalise whitespace and elide. The check catches absence, not punctuation."""
    result = resolver.resolve(
        Citation(
            type=CitationType.TREATY,
            instrument="rome_statute",
            article="8(2)(b)(iv)",
            quoted_text="intentionally launching an attack incidental loss of life civilians",
        )
    )
    assert result.status == CitationStatus.RESOLVED


def test_locator_formats_are_stable() -> None:
    """Locators are the citation's identity in logs, exports, and stored runs.

    Changing these formats breaks every persisted run artifact.
    """
    treaty = Citation(type=CitationType.TREATY, instrument="gc_iv", article="147")
    assert treaty.locator() == "gc_iv/art.147"

    case = Citation(
        type=CitationType.CASE, instrument="icty", case_id="icty_tadic_ad", paragraph="70"
    )
    assert case.locator() == "icty_tadic_ad/para.70"

    customary = Citation(type=CitationType.CUSTOMARY, instrument="icrc_customary", rule_number=14)
    assert customary.locator() == "customary_ihl/rule.14"
