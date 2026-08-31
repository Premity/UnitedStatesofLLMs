"""Attacker independence.

The proposal promises this measure explicitly: if the two attackers raise
substantially the same objections, then splitting doctrinal from evidentiary
challenge buys nothing and the second model is not earning its keep.

A negative result here is a real finding and should be reported as one. It is
also the most likely place for the design to be wrong, which makes it the most
valuable thing to measure honestly.
"""

from __future__ import annotations

from dataclasses import dataclass

from council_core.models.debate import Objection, Role


@dataclass(frozen=True)
class IndependenceResult:
    """Overlap between the two attackers' objection sets for one run."""

    jaccard: float
    """Token-level Jaccard over objection grounds. 0 = disjoint, 1 = identical."""

    target_overlap: float
    """Share of arguments both attackers chose to challenge. High values are not
    themselves a problem — a weak argument invites challenge from both angles —
    but combined with a high Jaccard they mean the mandates are not separating."""

    doctrinal_count: int
    evidentiary_count: int


def _tokens(text: str) -> set[str]:
    """Content tokens, lowercased, with legal stopwords removed.

    The stopword list is domain-specific on purpose: 'the argument fails
    because' appears in nearly every objection and would inflate every overlap
    score if left in.
    """
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "is",
        "that",
        "this",
        "it",
        "as",
        "for",
        "on",
        "with",
        "by",
        "at",
        "from",
        "not",
        "argument",
        "objection",
        "claim",
        "fails",
        "because",
        "therefore",
        "however",
        "moreover",
        "furthermore",
        "thus",
        "hence",
    }
    return {
        t for t in (w.strip(".,;:()[]\"'").lower() for w in text.split()) if t and t not in stop
    }


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two token sets."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def measure_independence(objections: list[Objection]) -> IndependenceResult:
    """Measure how much the two attackers overlapped in one run."""
    doctrinal = [o for o in objections if o.raised_by == Role.ATTACKER_DOCTRINAL]
    evidentiary = [o for o in objections if o.raised_by == Role.ATTACKER_EVIDENTIARY]

    doctrinal_tokens = set().union(*(_tokens(o.ground) for o in doctrinal)) if doctrinal else set()
    evidentiary_tokens = (
        set().union(*(_tokens(o.ground) for o in evidentiary)) if evidentiary else set()
    )

    doctrinal_targets = {o.target_argument_id for o in doctrinal}
    evidentiary_targets = {o.target_argument_id for o in evidentiary}
    union_targets = doctrinal_targets | evidentiary_targets

    return IndependenceResult(
        jaccard=jaccard(doctrinal_tokens, evidentiary_tokens),
        target_overlap=(
            len(doctrinal_targets & evidentiary_targets) / len(union_targets)
            if union_targets
            else 0.0
        ),
        doctrinal_count=len(doctrinal),
        evidentiary_count=len(evidentiary),
    )
