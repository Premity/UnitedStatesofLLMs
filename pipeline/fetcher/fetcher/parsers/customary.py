"""Turn the ICRC customary IHL database into a `CorpusDocument`.

The 161 rules of customary IHL are cited as `customary_ihl/rule.14`, a form
`Citation.locator()` has always produced and nothing has ever resolved -- the
rules were never indexed. This closes that.

Each rule node carries the rule itself inside a `<div class="Intro">`, followed
by the ICRC's commentary under `Practice`, `Summary` and so on. **Only the rule
is indexed.** The commentary is scholarship about the law, not the law, and a
quotation is checked against whatever the locator resolves to: including the
commentary would let a paraphrase of an ICRC gloss validate as the rule itself.
"""

from __future__ import annotations

import html
import re

from council_core.models.corpus import CorpusDocument, DocumentType, Span

CORPUS_ID = "customary_ihl"

# The rule statement, as distinct from the commentary that follows it.
INTRO_RE = re.compile(r'<div class="Intro">(.*?)</div>', re.S | re.IGNORECASE)
# Rules open with "Rule 14. ", which is the locator restated in prose.
PREFIX_RE = re.compile(r"^Rule\s+\d+[A-Za-z]?\.\s*", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def rule_text(body: str) -> str | None:
    """The rule itself, stripped of markup and of its 'Rule N.' prefix.

    A few rules state two limbs -- one for international and one for
    non-international armed conflict -- as `A.` and `B.` in separate divs,
    with "Rule N." alone in the first. Both limbs are the rule, so every Intro
    div is taken and joined.
    """
    divs = INTRO_RE.findall(body or "")
    if not divs:
        return None

    parts: list[str] = []
    for div in divs:
        text = html.unescape(_TAG.sub(" ", div))
        # str.split() collapses non-breaking spaces along with the rest.
        text = PREFIX_RE.sub("", " ".join(text.split())).strip()
        if text:
            parts.append(text)

    return "\n".join(parts) or None


def parse_customary_rules(
    *,
    entries: list[dict],
    title: str = "ICRC Study on Customary International Humanitarian Law",
    source_url: str = "https://ihl-databases.icrc.org/en/customary-ihl",
) -> CorpusDocument:
    """Build the customary IHL document from the API's rule nodes.

    Entries without a numeric rule number are skipped: the endpoint also
    carries section landing pages, which are navigation rather than law.
    """
    spans: list[Span] = []
    seen: set[int] = set()

    for entry in entries:
        raw_number = entry.get("field_rule_number")
        if raw_number is None or not str(raw_number).isdigit():
            continue
        number = int(raw_number)
        if number in seen:
            continue

        text = rule_text(entry.get("body") or "")
        if not text:
            continue

        spans.append(
            Span(
                locator=f"{CORPUS_ID}/rule.{number}",
                text=text,
                rule_number=number,
                heading=entry.get("title") or None,
            )
        )
        seen.add(number)

    spans.sort(key=lambda s: s.rule_number or 0)
    return CorpusDocument(
        id=CORPUS_ID,
        type=DocumentType.CUSTOMARY,
        title=title,
        source_url=source_url,
        spans=spans,
    )
