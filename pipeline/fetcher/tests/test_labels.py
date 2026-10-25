"""Sub-paragraph numbering.

Every failure here is silent. A label placed at the wrong depth produces a
locator no model will emit, so the provision is indexed and never retrieved;
a label dropped entirely loses the text. Neither raises.
"""

from __future__ import annotations

from fetcher.parsers.labels import parse_subparagraphs


def numbers(chunks: list[str]) -> list[str]:
    return [s.number for s in parse_subparagraphs(chunks)]


def test_arabic_paragraphs_are_numbered() -> None:
    assert numbers(["1. First.", "2. Second.", "3. Third."]) == ["(1)", "(2)", "(3)"]


def test_letters_nest_under_the_paragraph_that_introduces_them() -> None:
    chunks = ["2. For the purpose of this Statute:", "(a) First;", "(b) Second;"]
    assert numbers(chunks) == ["(2)", "(2)(a)", "(2)(b)"]


def test_romans_nest_under_letters() -> None:
    """The Rome Statute's article 8 shape: paragraph, letter, roman."""
    chunks = ["2. means:", "(a) Grave breaches:", "(i) Wilful killing;", "(ii) Torture;"]
    assert numbers(chunks) == ["(2)", "(2)(a)", "(2)(a)(i)", "(2)(a)(ii)"]


def test_a_letter_list_running_past_h_stays_letters() -> None:
    """`(i)` is both the ninth letter and the first roman numeral.

    Read as roman here, the item would be filed under `(1)(h)(i)` instead of
    `(1)(i)` -- a locator nobody cites.
    """
    chunks = ["1. intro:"] + [f"({c}) item;" for c in "abcdefghijk"]
    assert numbers(chunks)[-3:] == ["(1)(i)", "(1)(j)", "(1)(k)"]


def test_a_roman_list_opening_under_a_letter_is_roman() -> None:
    chunks = ["2. intro:", "(a) heading:", "(i) one;", "(ii) two;"]
    assert numbers(chunks) == ["(2)", "(2)(a)", "(2)(a)(i)", "(2)(a)(ii)"]


def test_a_second_letter_restarts_its_roman_list() -> None:
    chunks = ["2. x:", "(a) h:", "(i) one;", "(b) h2:", "(i) one again;"]
    assert numbers(chunks) == ["(2)", "(2)(a)", "(2)(a)(i)", "(2)(b)", "(2)(b)(i)"]


def test_returning_to_a_shallower_level_closes_the_deeper_one() -> None:
    """AP I article 51: paragraph 5 follows the (a)/(b)/(c) list under 4.

    If the list under 4 stayed open, 5 would be mis-filed beneath it.
    """
    chunks = [
        "4. Indiscriminate attacks are prohibited:",
        "(a) those not directed at a specific military objective;",
        "(b) those which employ a method which cannot be directed;",
        "5. Among others, the following are indiscriminate:",
        "(a) an attack by bombardment;",
    ]
    assert numbers(chunks) == ["(4)", "(4)(a)", "(4)(b)", "(5)", "(5)(a)"]


def test_an_unlabelled_clause_joins_the_provision_it_follows() -> None:
    """Articles often close a list with a clause belonging to the paragraph.

    It has no number of its own, so it cannot be its own span -- but dropping
    it would lose operative treaty text.
    """
    chunks = [
        "4. Indiscriminate attacks are:",
        "(a) those not directed at a military objective;",
        "and consequently are of a nature to strike without distinction.",
    ]
    subs = parse_subparagraphs(chunks)
    assert [s.number for s in subs] == ["(4)", "(4)(a)"]
    assert subs[-1].text.endswith("without distinction.")


def test_a_list_starting_part_way_through_is_still_captured() -> None:
    """An amendment quotes an article from the middle. Requiring a list to
    open at 1 dropped the text silently."""
    assert numbers(["2. second para", "3. third para"]) == ["(2)", "(3)"]


def test_a_paragraph_and_its_first_subparagraph_can_share_a_line() -> None:
    """Rome article 36(8) is written `8. (a) The States Parties shall...`.

    Dropping the inline `(a)` leaves the roman list beneath it with no letter
    parent, which minted `36(8)(i)(ii)` for what is really `36(8)(a)(ii)`.
    """
    chunks = [
        "8. (a) The States Parties shall take into account the need for:",
        "(i) The principal legal systems of the world;",
        "(ii) Equitable geographical representation; and",
        "(b) States Parties shall also take into account:",
    ]
    assert numbers(chunks) == ["(8)(a)", "(8)(a)(i)", "(8)(a)(ii)", "(8)(b)"]


def test_unnumbered_prose_yields_no_subparagraphs() -> None:
    """Most Geneva Convention articles are prose with no labels at all.

    The caller indexes those whole, at the article locator. Returning nothing
    is correct -- inventing `(1)` would create a locator nobody cites.
    """
    assert parse_subparagraphs(["Prisoners of war must at all times be humanely treated."]) == []


def test_blank_chunks_are_ignored() -> None:
    assert numbers(["1. First.", "", "   ", "2. Second."]) == ["(1)", "(2)"]


def test_depth_is_reported() -> None:
    subs = parse_subparagraphs(["2. x:", "(a) y:", "(i) z;"])
    assert [s.depth for s in subs] == [0, 1, 2]
