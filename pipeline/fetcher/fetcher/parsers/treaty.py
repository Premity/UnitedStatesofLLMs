"""Turn one ICRC treaty node into a `CorpusDocument`.

The ICRC serves a treaty as a flat list of entries, one per article, with the
article body as HTML. Two things have to happen here:

- **Articles become spans.** `field_treaty_content_unid` is `article-51` or
  `regulations-art-23`, which is the article number we build a locator from.
- **Articles that number their paragraphs are split further**, because a model
  cites `51(2)` and the resolver must find exactly that. Articles written as
  unnumbered prose -- most of the Geneva Conventions -- are kept whole, since
  inventing `(1)` would create a locator nobody cites.

Both the whole article and each of its paragraphs are indexed. ADR 0008 makes
them distinct locators: `ap_i/art.51` does not resolve `ap_i/art.51(2)`, and a
quotation is checked against whichever one was cited.
"""

from __future__ import annotations

import html
import re

from council_core.models.corpus import CorpusDocument, DocumentType, Span
from fetcher.parsers.labels import parse_subparagraphs

# `article-51`, `article-8bis`, `regulations-art-23`.
UNID_RE = re.compile(r"^(?:article|regulations-art)-(.+)$", re.IGNORECASE)

_BLOCK_END = re.compile(r"</(?:p|li|div|tr)>|<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def html_to_chunks(markup: str) -> list[str]:
    """Flatten an article's HTML into the lines its labels sit on.

    Sub-paragraphs are not reliably their own elements: the Rome Statute gives
    one `<p>` per item, while AP I packs `(a)`, `(b)` and `(c)` into a single
    `<p>` separated by newlines. Splitting on both block ends and newlines
    handles the two shapes with one rule.
    """
    if not markup:
        return []
    text = _BLOCK_END.sub("\n", markup)
    text = html.unescape(_TAG.sub("", text))
    text = text.replace("\xa0", " ")
    return [line.strip() for line in text.split("\n") if line.strip()]


def article_number(unid: str) -> str | None:
    """The article number from an entry's unid, or None if it is not an article."""
    m = UNID_RE.match(unid or "")
    return m.group(1).strip() if m else None


def parse_treaty(
    *,
    corpus_id: str,
    title: str,
    source_url: str,
    entries: list[dict],
    section: str = "Article",
    year: int | None = None,
) -> CorpusDocument:
    """Build a document from one treaty node's entries.

    `section` selects which entries belong to this document. Hague IV is two
    corpus ids served by one node, so the Convention takes `Article` and the
    annexed Regulations take `Annex` (ADR 0010).
    """
    spans: list[Span] = []
    seen: set[str] = set()

    for entry in entries:
        if entry.get("field_treaty_content_section") != section:
            continue

        number = article_number(entry.get("field_treaty_content_unid") or "")
        if number is None:
            continue

        chunks = html_to_chunks(entry.get("field_treaty_content_content") or "")
        if not chunks:
            continue

        heading = entry.get("field_treaty_content_title") or None
        article_locator = f"{corpus_id}/art.{number}"

        # The whole article, so a citation to `art.51` resolves.
        if article_locator not in seen:
            spans.append(
                Span(
                    locator=article_locator,
                    text="\n".join(chunks),
                    article=number,
                    heading=heading,
                )
            )
            seen.add(article_locator)

        # Then each numbered paragraph, where the article has them.
        for sub in parse_subparagraphs(chunks):
            if not sub.number:
                continue
            locator = f"{corpus_id}/art.{number}{sub.number}"
            if locator in seen:
                continue
            spans.append(
                Span(
                    locator=locator,
                    text=sub.text,
                    article=f"{number}{sub.number}",
                    parent=article_locator,
                )
            )
            seen.add(locator)

    return CorpusDocument(
        id=corpus_id,
        type=DocumentType.TREATY,
        title=title,
        source_url=source_url,
        year=year,
        spans=spans,
    )
