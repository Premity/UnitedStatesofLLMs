"""Citation validity metrics.

Fully automatic — no human grading — and it measures the exact failure mode the
project names in its abstract: drift into fabricated authority.

The three statuses stay separate throughout. `unresolved` is the fabrication
signal; `out_of_corpus` only means the claim could not be checked here. Merging
them would let a system look worse simply for citing real authority the corpus
does not happen to index.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from council_core.models.citation import CitationStatus, ResolvedCitation


@dataclass(frozen=True)
class CitationMetrics:
    """Citation health for one arm."""

    total: int
    resolved: int
    unresolved: int
    out_of_corpus: int
    misquoted: int

    @property
    def validity_rate(self) -> float:
        """Share of citations that resolved cleanly."""
        return self.resolved / self.total if self.total else float("nan")

    @property
    def fabrication_rate(self) -> float:
        """Share that pointed at an indexed instrument but did not exist there.

        The headline anti-hallucination number.
        """
        return (self.unresolved + self.misquoted) / self.total if self.total else float("nan")


def measure_citations(resolved: list[ResolvedCitation]) -> CitationMetrics:
    """Tally citation statuses across a run or an arm."""
    counts = Counter(rc.status for rc in resolved)

    return CitationMetrics(
        total=len(resolved),
        resolved=counts[CitationStatus.RESOLVED],
        unresolved=counts[CitationStatus.UNRESOLVED],
        out_of_corpus=counts[CitationStatus.OUT_OF_CORPUS],
        misquoted=counts[CitationStatus.MISQUOTED],
    )
