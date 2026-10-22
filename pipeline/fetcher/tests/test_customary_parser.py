"""The 161 customary IHL rules.

`Citation.locator()` has always rendered `customary_ihl/rule.14`. Until these
were indexed nothing resolved it, so a model citing a real customary rule was
scored as inventing authority.
"""

from __future__ import annotations

from fetcher.parsers.customary import parse_customary_rules, rule_text

from council_core.models.corpus import DocumentType

RULE_14 = (
    '<div class="Intro">Rule 14. Launching an attack which may be expected to cause '
    "incidental loss of civilian life, which would be excessive in relation to the "
    "concrete and direct military advantage anticipated, is prohibited.</div>"
    '<h3 class="L3">Practice</h3><div class="Normal">Volume II, Chapter 4.</div>'
    '<h3 class="L3">Summary</h3><div class="Normal">State practice establishes this '
    "rule as a norm of customary international law.</div>"
)

# A few rules state two limbs across separate divs, with "Rule N." alone first.
RULE_129 = (
    '<div class="Note">Note: This chapter addresses forced displacement.</div>'
    '<div class="Intro">Rule 129.</div>'
    '<div class="Intro">A. Parties to an international armed conflict may not deport '
    "civilians.</div>"
    '<div class="Intro">B. Parties to a non-international armed conflict may not order '
    "displacement.</div>"
    '<div class="Normal">Volume II, Chapter 38.</div>'
)


def entry(number: int | str | None, body: str, title: str = "A rule") -> dict:
    return {"field_rule_number": number, "body": body, "title": title}


def test_the_locator_is_what_a_model_cites() -> None:
    doc = parse_customary_rules(entries=[entry(14, RULE_14)])
    assert doc.spans[0].locator == "customary_ihl/rule.14"
    assert doc.type is DocumentType.CUSTOMARY


def test_only_the_rule_is_indexed_not_the_commentary() -> None:
    """The ICRC's Practice and Summary sections are scholarship about the law,
    not the law. Indexing them would let a paraphrase of a gloss validate as a
    quotation of the rule itself.
    """
    text = parse_customary_rules(entries=[entry(14, RULE_14)]).spans[0].text
    assert "excessive in relation to the concrete" in text
    assert "Volume II" not in text
    assert "State practice establishes" not in text


def test_the_rule_number_prefix_is_stripped() -> None:
    """ "Rule 14." is the locator restated in prose; the locator already says it."""
    assert not parse_customary_rules(entries=[entry(14, RULE_14)]).spans[0].text.startswith("Rule")


def test_both_limbs_of_a_two_part_rule_are_kept() -> None:
    """Rules 124 and 129 split into A (international) and B (non-international)
    across separate divs. Taking only the first silently loses half the rule --
    and the half covering non-international conflict at that."""
    text = parse_customary_rules(entries=[entry(129, RULE_129)]).spans[0].text
    assert "A. Parties to an international" in text
    assert "B. Parties to a non-international" in text


def test_a_leading_note_div_does_not_displace_the_rule() -> None:
    doc = parse_customary_rules(entries=[entry(129, RULE_129)])
    assert "This chapter addresses" not in doc.spans[0].text


def test_non_numeric_entries_are_skipped() -> None:
    """The endpoint also serves section landing pages, which are navigation."""
    doc = parse_customary_rules(
        entries=[entry(None, '<div class="Intro">A section.</div>'), entry(14, RULE_14)]
    )
    assert [s.rule_number for s in doc.spans] == [14]


def test_rules_come_out_in_order() -> None:
    doc = parse_customary_rules(entries=[entry(14, RULE_14), entry(1, RULE_14), entry(7, RULE_14)])
    assert [s.rule_number for s in doc.spans] == [1, 7, 14]


def test_duplicate_rule_numbers_are_ignored() -> None:
    doc = parse_customary_rules(entries=[entry(14, RULE_14), entry(14, RULE_14)])
    assert len(doc.spans) == 1


def test_a_rule_with_no_intro_is_skipped_rather_than_guessed() -> None:
    """Better a missing rule than a span holding commentary under a rule
    locator, which would validate the wrong text."""
    assert parse_customary_rules(entries=[entry(99, '<div class="Normal">x</div>')]).spans == []


def test_rule_text_returns_none_without_an_intro() -> None:
    assert rule_text('<div class="Normal">Commentary only.</div>') is None
    assert rule_text("") is None
