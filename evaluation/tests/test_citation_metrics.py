"""Tests for citation validity metrics (T2-2).

Verifies that:
1. `unresolved` and `out_of_corpus` are tracked as separate, distinct counts.
2. `fabrication_rate` ignores `out_of_corpus` entirely and counts only
   `unresolved`; `misquoted` is reported apart as `misquote_rate`.
3. Edge cases: all-resolved, all-out-of-corpus, empty lists.
"""

from __future__ import annotations

import math

from council_core.models.citation import (
    Citation,
    CitationStatus,
    CitationType,
    ResolvedCitation,
)
from metrics.citations import CitationMetrics, measure_citations


def _make_resolved(
    status: CitationStatus,
    *,
    instrument: str = "ap_i",
    article: str = "51(2)",
    quote: str | None = "civilians shall not be the object of attack",
) -> ResolvedCitation:
    """Helper to construct a ResolvedCitation with a given status."""
    return ResolvedCitation(
        citation=Citation(
            type=CitationType.TREATY,
            instrument=instrument,
            article=article,
            quoted_text=quote,
        ),
        status=status,
        corpus_text="authoritative span" if status == CitationStatus.RESOLVED else None,
    )


class TestCitationMetrics:
    """Tests for measuring citation health and fabrication rates."""

    def test_unresolved_and_out_of_corpus_are_counted_separately(self) -> None:
        """Proves that unresolved and out_of_corpus are separate categories in counts."""
        citations = [
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.OUT_OF_CORPUS, instrument="geneva_convention_1864"),
            _make_resolved(CitationStatus.OUT_OF_CORPUS, instrument="customary_rule_external"),
            _make_resolved(CitationStatus.OUT_OF_CORPUS, instrument="lieber_code"),
            _make_resolved(CitationStatus.UNRESOLVED, article="999"),
            _make_resolved(CitationStatus.UNRESOLVED, article="888"),
            _make_resolved(CitationStatus.MISQUOTED, quote="completely invented quote"),
        ]

        metrics = measure_citations(citations)

        assert isinstance(metrics, CitationMetrics)
        assert metrics.total == 10
        assert metrics.resolved == 4
        assert metrics.out_of_corpus == 3
        assert metrics.unresolved == 2
        assert metrics.misquoted == 1

        # The counts must not collapse or alias
        assert metrics.unresolved != metrics.out_of_corpus
        assert metrics.unresolved + metrics.out_of_corpus == 5

    def test_fabrication_rate_ignores_out_of_corpus_entirely(self) -> None:
        """Out-of-corpus citations affect neither the fabrication numerator nor denominator.

        Fabrication rate measures hallucinated authority (unresolved only).
        Authority that is real but unindexed (out_of_corpus) cannot be verified,
        but is explicitly not fabrication (ADR 0004 & Non-negotiable #2).
        """
        # Baseline: 5 citations: 3 resolved, 1 unresolved, 1 misquoted
        # fabrication_rate = 1 / 5 = 0.20; misquote_rate = 1 / 5 = 0.20
        base_citations = [
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.UNRESOLVED, article="999"),
            _make_resolved(CitationStatus.MISQUOTED, quote="wrong quote"),
        ]
        base_metrics = measure_citations(base_citations)
        assert base_metrics.total == 5
        assert base_metrics.fabrication_rate == 0.20
        assert base_metrics.misquote_rate == 0.20

        # Adding out-of-corpus citations does not change the rate because they
        # are excluded from both the numerator and denominator.
        with_ooc = base_citations + [
            _make_resolved(CitationStatus.OUT_OF_CORPUS, instrument=f"external_{i}")
            for i in range(5)
        ]
        ooc_metrics = measure_citations(with_ooc)

        assert ooc_metrics.total == 10
        assert ooc_metrics.out_of_corpus == 5
        assert ooc_metrics.unresolved == 1
        assert ooc_metrics.misquoted == 1
        assert ooc_metrics.fabrication_rate == base_metrics.fabrication_rate == 0.20
        assert ooc_metrics.misquote_rate == base_metrics.misquote_rate == 0.20

    def test_all_out_of_corpus_has_no_eligible_fabrication_rate(self) -> None:
        """An all-out-of-corpus set has no eligible denominator."""
        citations = [
            _make_resolved(CitationStatus.OUT_OF_CORPUS, instrument=f"treaty_{i}") for i in range(4)
        ]
        metrics = measure_citations(citations)

        assert metrics.total == 4
        assert metrics.out_of_corpus == 4
        assert metrics.resolved == 0
        assert metrics.unresolved == 0
        assert metrics.misquoted == 0

        assert metrics.validity_rate == 0.0
        assert math.isnan(metrics.fabrication_rate)

    def test_misquoted_citations_are_not_fabrication(self) -> None:
        """Pins the definition: fabrication is `unresolved` only (ADR 0004).

        A misquote still lowers the validity rate and has its own rate, so it is
        reported, just not mixed into the headline number.
        """
        citations = [
            _make_resolved(CitationStatus.RESOLVED),
            _make_resolved(CitationStatus.MISQUOTED, quote="incorrect quotation"),
        ]
        metrics = measure_citations(citations)

        assert metrics.fabrication_rate == 0.0
        assert metrics.misquote_rate == 0.5
        assert metrics.validity_rate == 0.5

    def test_all_resolved_clean(self) -> None:
        """100% validity, 0% fabrication."""
        citations = [_make_resolved(CitationStatus.RESOLVED) for _ in range(5)]
        metrics = measure_citations(citations)

        assert metrics.total == 5
        assert metrics.validity_rate == 1.0
        assert metrics.fabrication_rate == 0.0

    def test_all_fabricated(self) -> None:
        """100% fabrication rate."""
        citations = [
            _make_resolved(CitationStatus.UNRESOLVED),
            _make_resolved(CitationStatus.UNRESOLVED),
            _make_resolved(CitationStatus.UNRESOLVED),
        ]
        metrics = measure_citations(citations)

        assert metrics.total == 3
        assert metrics.validity_rate == 0.0
        assert metrics.fabrication_rate == 1.0
        assert metrics.misquote_rate == 0.0

    def test_empty_citations_return_nan_rates(self) -> None:
        """Empty list handles zero-division with NaN."""
        metrics = measure_citations([])

        assert metrics.total == 0
        assert metrics.resolved == 0
        assert metrics.unresolved == 0
        assert metrics.out_of_corpus == 0
        assert metrics.misquoted == 0
        assert math.isnan(metrics.validity_rate)
        assert math.isnan(metrics.fabrication_rate)
        assert math.isnan(metrics.misquote_rate)
