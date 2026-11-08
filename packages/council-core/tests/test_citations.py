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

    assert (
        Citation(type=CitationType.TREATY, instrument="ap_i", article="51(2)").locator()
        == "ap_i/art.51(2)"
    )


def test_redundant_article_prefix_is_normalized_once_at_construction() -> None:
    """A model-supplied 'art.51(2)' must not double up with locator()'s own 'art.' label.

    Normalizing at the field (not just inside locator()) means the stored field,
    the frontend, and any export that reads `.article` directly all see the
    clean value too (GitHub #11-1).
    """
    treaty = Citation(type=CitationType.TREATY, instrument="ap_i", article="art.51(2)")
    assert treaty.article == "51(2)"
    assert treaty.locator() == "ap_i/art.51(2)"

    assert Citation(
        type=CitationType.TREATY, instrument="ap_i", article="Article 51(2)"
    ).article == ("51(2)")


def test_article_prefix_normalization_does_not_mangle_non_prefixed_values() -> None:
    """A value that merely starts with 'art' must survive untouched (GitHub #8)."""
    assert Citation(type=CitationType.TREATY, instrument="x", article="artifact-3").article == (
        "artifact-3"
    )
    assert (
        Citation(type=CitationType.TREATY, instrument="x", article="articles 51 and 52").article
        == "articles 51 and 52"
    )


def test_a_doubled_article_prefix_normalizes_to_a_stable_locator() -> None:
    """Stripping must be idempotent, or one artifact yields two locators.

    Matching a single prefix left `art.art.51` as `art.51` -- still prefixed,
    so the next validation pass stripped again. A stored run then resolved
    `gc_iv/art.art.51` on the first read and `gc_iv/art.51` after a load/save
    cycle, which silently changes a citation's status (and so the fabrication
    metric) for an artifact nobody edited.
    """
    once = Citation(type=CitationType.TREATY, instrument="gc_iv", article="art.art.51")
    twice = Citation.model_validate_json(once.model_dump_json())

    assert once.article == twice.article == "51"
    assert once.locator() == twice.locator() == "gc_iv/art.51"


def test_spaced_and_mixed_doubled_prefixes_are_also_stripped_whole() -> None:
    """The repeated form has to cover the spellings a model actually mixes."""
    for raw in ("art. art. 51", "Article art.51", "art.art.art.8(2)(b)"):
        article = Citation(type=CitationType.TREATY, instrument="x", article=raw).article
        assert article is not None
        assert not article.lower().startswith("art"), raw
