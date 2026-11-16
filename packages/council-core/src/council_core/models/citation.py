"""Citation schema and resolution status.

Citations are *structured*, never free prose. A model that wants to cite
Article 8(2)(b)(iv) of the Rome Statute must emit the fields below, not a
sentence. That is what makes fabricated authority detectable: every citation
is looked up in the corpus index, and one that does not resolve is flagged
rather than silently believed.

See `council_core.citations` for the resolver and `docs/adr/0004-citation-integrity.md`
for why this is a first-class module.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# Requires a delimiter (`.` or whitespace) after 'art'/'article', so a value
# that merely starts with those letters -- "artifact-3", "articles 51" -- is
# left alone. An earlier version matched the bare letters with no delimiter
# required and silently mangled both (GitHub #8).
#
# The group repeats (`+`) so the strip is idempotent. Matching a single prefix
# left `art.art.51` as `art.51`, which still carries a prefix: the field then
# normalized further on every later validation pass, so one stored artifact
# produced a different locator before and after a load/save cycle -- and
# locators are permanent (see `locator()`).
_ARTICLE_PREFIX_RE = re.compile(r"^(?:\s*art(?:icle)?(?:\.|\s)\s*)+", re.IGNORECASE)


def _strip_article_prefix(article: str | None) -> str | None:
    """Drop a redundant 'art.'/'article' prefix a model put inside the field.

    `locator()` always prepends 'art.' itself. A model echoing its own prose
    ("Article 51(2) of Additional Protocol I") sometimes puts 'art.51(2)' in
    the structured field instead of '51(2)', which then doubles up to
    'ap_i/art.art.51(2)' -- a locator nothing in the index can match. A real
    provision then resolves as fabricated. Confirmed live: round 1 of a real
    debate produced the clean form, round 2 (rebuttal, with the model's own
    prior natural-language reasoning in context) produced the doubled one for
    every citation in that turn.
    """
    if article is None:
        return None
    return _ARTICLE_PREFIX_RE.sub("", article)


class CitationType(StrEnum):
    """What kind of authority is being cited.

    The type determines which locator fields are meaningful and how the
    resolver addresses the corpus.
    """

    TREATY = "treaty"
    """Treaty or convention text — addressed by instrument + article."""

    CASE = "case"
    """Judgment or advisory opinion — addressed by case id + paragraph."""

    CUSTOMARY = "customary"
    """ICRC customary IHL rule — addressed by rule number."""

    RESOLUTION = "resolution"
    """UN resolution — addressed by body + resolution number."""


class CitationStatus(StrEnum):
    """Outcome of resolving a citation against the corpus index."""

    RESOLVED = "resolved"
    """The locator exists in the corpus and the quoted span was retrieved."""

    UNRESOLVED = "unresolved"
    """The locator does not exist in the corpus. Treated as unsupported."""

    OUT_OF_CORPUS = "out_of_corpus"
    """The instrument is real but outside the indexed corpus (Tier 3).

    Distinct from UNRESOLVED: this is not evidence of fabrication, only that
    the claim cannot be verified here. Reported separately in metrics.
    """

    MISQUOTED = "misquoted"
    """The locator resolves, but the model's quoted text does not match the span."""


class Citation(BaseModel):
    """A structured reference to legal authority, as emitted by a model.

    Locator fields are deliberately loose (all optional strings) because the
    meaningful set varies by `type`. The resolver is responsible for rejecting
    a citation whose locator is incomplete for its type.
    """

    type: CitationType
    instrument: str = Field(
        description="Canonical instrument slug, e.g. 'rome_statute', 'gc_iv', 'ap_i'."
    )
    article: str | None = Field(
        default=None,
        description="Article locator for treaties, e.g. '8(2)(b)(iv)'.",
    )

    @field_validator("article")
    @classmethod
    def _normalize_article(cls, value: str | None) -> str | None:
        """Strip a redundant 'art.' prefix once, at construction.

        Previously only `locator()` stripped it, so the stored field (and
        every renderer that reads `article` directly instead of calling
        `locator()`) kept the raw 'art.51(2)', which then doubled with the
        label those renderers prepend themselves (GitHub #11-1).
        """
        return _strip_article_prefix(value)

    case_id: str | None = Field(
        default=None,
        description="Canonical case slug for jurisprudence, e.g. 'icty_galic_tj'.",
    )
    paragraph: str | None = Field(
        default=None,
        description="Paragraph number within a judgment, e.g. '58'.",
    )
    rule_number: int | None = Field(
        default=None,
        description="ICRC customary IHL rule number, 1-161.",
    )
    quoted_text: str | None = Field(
        default=None,
        description="The span the model claims this locator contains. Checked when present.",
    )

    def locator_gap(self) -> str | None:
        """Why this citation lacks a field its type requires, or None if it does not."""
        match self.type:
            case CitationType.TREATY if not self.article:
                return "Treaty citation is missing an article locator."
            case CitationType.CASE if not (self.case_id and self.paragraph):
                return "Case citation requires both a case id and a paragraph."
            case CitationType.CUSTOMARY if self.rule_number is None:
                return "Customary IHL citation is missing a rule number."
            case _:
                return None

    def format_problem(self) -> str | None:
        """Why this citation is malformed as emitted, or None if it is well formed.

        Checked when a model's reply is parsed, so a malformed citation goes
        back to the model to correct rather than reaching the resolver, which
        scores an incomplete citation `unresolved`, the fabrication signal. A
        real provision in the wrong shape is not a fabrication; an invented one
        still fails to resolve once it is well formed.
        """
        if gap := self.locator_gap():
            return gap
        if "/" in self.instrument:
            return (
                f"'instrument' must be the instrument's id alone, e.g. 'ap_i', not a locator "
                f"('{self.instrument}'); put the article in 'article'."
            )
        return None

    def locator(self) -> str:
        """Render a stable, human-readable locator string.

        Used as the citation's identity in logs, exports, and metrics.
        """
        match self.type:
            case CitationType.TREATY:
                return f"{self.instrument}/art.{self.article}"
            case CitationType.CASE:
                return f"{self.case_id}/para.{self.paragraph}"
            case CitationType.CUSTOMARY:
                return f"customary_ihl/rule.{self.rule_number}"
            case CitationType.RESOLUTION:
                return f"{self.instrument}/{self.article or ''}".rstrip("/")


class ResolvedCitation(BaseModel):
    """A citation after the validator has attempted to resolve it.

    Carries the original citation plus the verdict and, when resolution
    succeeded, the actual corpus text — which is what the frontend shows on
    hover and what a reviewer checks the argument against.
    """

    citation: Citation
    status: CitationStatus
    corpus_text: str | None = Field(
        default=None,
        description="The authoritative text at this locator, when resolved.",
    )
    source_url: str | None = Field(
        default=None,
        description="Link to the public source document, when known.",
    )
    note: str | None = Field(
        default=None,
        description="Why resolution failed, when it did.",
    )

    @property
    def is_supported(self) -> bool:
        """Whether an argument resting on this citation may be treated as grounded."""
        return self.status == CitationStatus.RESOLVED


def malformed_citations(items: list[tuple[str, list[Citation]]]) -> str | None:
    """Every malformed citation in a model's reply, as one message for the repair prompt.

    `items` pairs a label ("arguments[0]") with that item's citations. Returns
    None when all are well formed.
    """
    problems = [
        f"{label}.citations[{i}]: {problem}"
        for label, citations in items
        for i, citation in enumerate(citations)
        if (problem := citation.format_problem())
    ]
    if not problems:
        return None
    return (
        "Malformed citations:\n- "
        + "\n- ".join(problems)
        + '\nA treaty article is {"type": "treaty", "instrument": "ap_i", "article": "51(2)"};'
        " copy the instrument and article from the retrieved context heading"
        " [<instrument>/art.<article>]."
    )
