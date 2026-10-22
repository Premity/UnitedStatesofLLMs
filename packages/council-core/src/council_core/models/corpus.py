"""The shape every corpus source normalises to.

A fetcher's job is to turn whatever a source gives it -- HTML, PDF, an API
response -- into a `CorpusDocument`. Everything downstream reads this and never
the source format, so adding a source means writing a parser, not touching the
indexer.

`locator` is the join key. It is what the citation index maps, what models emit
when they cite, and what the resolver looks up. It must be exactly what
`Citation.locator()` renders for the same provision -- see ADR 0008 -- or a
correct citation resolves as a fabrication.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

# Matches the two locator forms in ADR 0008:
#   <instrument>/art.<article>    ap_i/art.51(2), rome_statute/art.8(2)(b)(iv)
#   <case_id>/para.<paragraph>    icty_galic_tj/para.58
#
# Sub-paragraphs are parenthesised, so `ap_i/art.51.2` and `ap_i/art.51/para.2`
# are rejected rather than silently indexed alongside `ap_i/art.51(2)` -- two
# spellings of one provision means half the citations to it miss.
LOCATOR_RE = re.compile(
    r"^[a-z0-9_]+/(?:"
    r"art\.[0-9]+[a-z]?(?:\s?(?:bis|ter|quater))?(?:\([0-9A-Za-z]+\))*"
    r"|para\.[0-9]+[a-z]?"
    r")$"
)


class DocumentType(StrEnum):
    """What kind of authority a document is. Determines the locator form."""

    TREATY = "treaty"
    CASE = "case"
    RESOLUTION = "resolution"


class Span(BaseModel):
    """One citable unit: a treaty article, or a numbered judgment paragraph.

    The span -- not the document -- is the unit of retrieval and of citation
    resolution. Chunking at any coarser granularity makes
    `icty_galic_tj/para.58` unresolvable; see non-negotiable #4.
    """

    locator: str = Field(description="Canonical locator, e.g. 'ap_i/art.51(2)'.")
    text: str = Field(description="The provision's text, verbatim from the source.")

    article: str | None = Field(
        default=None, description="Article locator for treaty spans, e.g. '8(2)(b)(iv)'."
    )
    paragraph: str | None = Field(
        default=None, description="Paragraph number for case spans, e.g. '58'."
    )
    heading: str | None = Field(
        default=None, description="The provision's own title, where the source gives one."
    )
    parent: str | None = Field(
        default=None,
        description=(
            "Locator of the enclosing provision, e.g. 'ap_i/art.51' for 'ap_i/art.51(2)'. "
            "Gives the embedder context for a one-line article without merging spans."
        ),
    )

    @field_validator("locator", "parent")
    @classmethod
    def _locator_is_well_formed(cls, v: str | None) -> str | None:
        if v is not None and not LOCATOR_RE.match(v):
            raise ValueError(
                f"Locator {v!r} does not match ADR 0008. Expected '<instrument>/art.<article>' "
                "or '<case_id>/para.<paragraph>'."
            )
        return v

    @field_validator("text")
    @classmethod
    def _text_is_not_blank(cls, v: str) -> str:
        # A blank span resolves as `misquoted` for every quotation against it,
        # which reads in the metrics as the model misquoting the law.
        if not v.strip():
            raise ValueError("Span text is empty. A span with no text cannot be cited against.")
        return v


class CorpusDocument(BaseModel):
    """One instrument or judgment, split into citable spans."""

    id: str = Field(description="Corpus id from the manifest, e.g. 'ap_i'. Permanent (ADR 0007).")
    type: DocumentType
    title: str
    source_url: str = Field(description="Where the text came from, for attribution and re-fetch.")

    year: int | None = None
    court: str | None = Field(default=None, description="For judgments: 'ICTY', 'ICC', …")
    spans: list[Span] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_is_a_slug(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError(f"Corpus id {v!r} must be lowercase snake_case (ADR 0007).")
        return v

    @model_validator(mode="after")
    def _spans_belong_to_this_document(self) -> CorpusDocument:
        """Every span's locator must start with this document's id.

        A span filed under the wrong document is indexed under a locator nobody
        cites, so the provision silently goes missing from the corpus.
        """
        # A treaty is cited by article and a judgment by paragraph. Mixing the
        # forms produces a locator no model will ever emit, so the provision is
        # indexed but unreachable.
        expected = "para." if self.type is DocumentType.CASE else "art."

        seen: set[str] = set()
        for span in self.spans:
            prefix, _, tail = span.locator.partition("/")
            if not tail.startswith(expected):
                raise ValueError(
                    f"Span {span.locator!r} uses the wrong locator form for a "
                    f"{self.type.value} document; expected '{self.id}/{expected}…'."
                )
            if prefix != self.id:
                raise ValueError(
                    f"Span locator {span.locator!r} does not belong to document {self.id!r}."
                )
            if span.locator in seen:
                raise ValueError(f"Duplicate span locator {span.locator!r} in {self.id!r}.")
            seen.add(span.locator)
        return self

    def locators(self) -> list[str]:
        """Every locator this document provides, in order."""
        return [s.locator for s in self.spans]
