"""Turn a treaty article's text into numbered sub-paragraphs.

A citation names a provision -- `8(2)(b)(iv)` -- so the index has to hold that
provision and not the article it sits in. The source gives us an article's body
as a flat run of labelled chunks, so the nesting has to be recovered from the
labels themselves.

Three label styles appear, and they nest in this order:

    1.      arabic     the paragraph
    (a)     letter     a sub-paragraph
    (i)     roman      a sub-sub-paragraph

The ambiguity that matters: `(i)`, `(v)` and `(x)` are both roman numerals and
letters of the alphabet. `(a) (b) (c) ... (h) (i)` is a letter list reaching i,
while `(i) (ii) (iii)` is a roman list starting at i. Guessing wrong puts the
text under a locator nobody cites, which reads downstream as the model citing
something that does not exist.

The rule used here is positional rather than lexical: a label continues the
list it is a plausible successor to. `(i)` after `(h)` continues the letters;
`(i)` directly under a letter item opens a roman list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A label sits at the very start of a chunk: "1. ", "(a) ", "(iv) ".
ARABIC = re.compile(r"^(\d+)\.\s+")
BRACKETED = re.compile(r"^\(([a-z]+|[ivxlc]+)\)\s+", re.IGNORECASE)

ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def _roman_to_int(s: str) -> int | None:
    """Parse a lowercase roman numeral, or None if it is not one."""
    if not s or any(ch not in ROMAN_VALUES for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN_VALUES[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def _letter_to_int(s: str) -> int | None:
    """Parse a single-letter list marker: a -> 1, b -> 2."""
    return ord(s) - 96 if len(s) == 1 and "a" <= s <= "z" else None


@dataclass
class _Level:
    """One open list: its kind, and how far it has counted."""

    kind: str  # "arabic" | "letter" | "roman"
    label: str
    index: int


@dataclass
class Subparagraph:
    """One citable piece of an article.

    `number` is the locator suffix as it is cited -- `(2)(b)(iv)` -- so the
    article number plus this is the full locator: `8` + `(2)(b)(iv)`.
    A chunk that is the whole article body carries an empty `number`.
    """

    number: str
    text: str
    depth: int = 0
    labels: list[str] = field(default_factory=list)


class _Stack:
    """The open label lists, outermost first."""

    def __init__(self) -> None:
        self._levels: list[_Level] = []

    def place(self, kind: str, label: str) -> list[str] | None:
        """Fit a label into the nesting, returning the full label path.

        None means the label does not continue or open any list we can see,
        so the chunk is treated as continuation text rather than a new
        provision.
        """
        value = _letter_to_int(label) if kind == "letter" else _roman_to_int(label)
        if kind == "arabic":
            value = int(label)

        # Continue an open list at the depth where it was last seen.
        for depth, level in enumerate(self._levels):
            if level.kind == kind and value == level.index + 1:
                self._levels = self._levels[:depth]
                self._levels.append(_Level(kind, label, value))
                return [lv.label for lv in self._levels]

        if value is None:
            return None

        # A new list opens at 1.
        if value == 1:
            self._levels.append(_Level(kind, label, value))
            return [lv.label for lv in self._levels]

        # Opening above 1 happens when text is quoted from part-way through:
        # an amendment restating `(b)` onwards, or an article beginning at
        # paragraph 2. It is only safe where no list of this kind is already
        # running -- otherwise `(i)` followed by `(iv)` would read as a nested
        # list and mint `(i)(iv)`, a locator that addresses nothing.
        if not any(lv.kind == kind for lv in self._levels):
            self._levels.append(_Level(kind, label, value))
            return [lv.label for lv in self._levels]

        return None


def _candidates(label: str) -> list[tuple[str, str]]:
    """The readings of a bracketed label, most likely first.

    `(i)` is both a letter and a roman numeral, so both readings are offered
    and the stack decides which one fits.
    """
    lower = label.lower()
    readings: list[tuple[str, str]] = []
    if _letter_to_int(lower) is not None:
        readings.append(("letter", lower))
    if _roman_to_int(lower) is not None:
        readings.append(("roman", lower))
    return readings


def parse_subparagraphs(chunks: list[str]) -> list[Subparagraph]:
    """Split an article's chunks into numbered provisions.

    An unlabelled chunk, or one whose label fits nowhere, is appended to the
    provision it follows -- treaty articles often close a list with a clause
    that belongs to the paragraph introducing it.
    """
    out: list[Subparagraph] = []
    stack = _Stack()

    for chunk in chunks:
        text = chunk.strip()
        if not text:
            continue

        labels: list[str] | None = None
        body = text

        if m := ARABIC.match(text):
            labels = stack.place("arabic", m.group(1))
            if labels is not None:
                body = text[m.end() :].strip()
                # Some articles open a paragraph and its first sub-paragraph
                # on one line: "8. (a) The States Parties shall...". Dropping
                # the `(a)` leaves any roman list under it with no letter
                # parent, so `(8)(a)(ii)` would be minted as `(8)(i)(ii)`.
                if inner := BRACKETED.match(body):
                    for kind, label in _candidates(inner.group(1)):
                        if (placed := stack.place(kind, label)) is not None:
                            labels, body = placed, body[inner.end() :].strip()
                            break
        elif m := BRACKETED.match(text):
            raw = m.group(1)
            for kind, label in _candidates(raw):
                if (placed := stack.place(kind, label)) is not None:
                    labels, body = placed, text[m.end() :].strip()
                    break

        if labels is None:
            if out:
                out[-1].text += "\n" + text
            continue

        out.append(
            Subparagraph(
                number="".join(f"({x})" for x in labels),
                text=body,
                depth=len(labels) - 1,
                labels=list(labels),
            )
        )

    return out
