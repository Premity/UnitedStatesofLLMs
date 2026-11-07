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
_ARTICLE_PREFIX_RE = re.compile(r"^\s*art(?:icle)?(?:\.|\s)\s*", re.IGNORECASE)


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
