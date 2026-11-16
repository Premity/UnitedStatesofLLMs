"""Judge conclusions the outcome parser once misscored, taken from real runs.

The judge is told to open with "Yes.", "No." or "Indeterminate.", and these
did. The parser still read the first two as the wrong outcome and the "lawful"
cases as indeterminate. Accuracy and Brier are computed from this mapping, so
a misread verdict is a wrong measurement, not a wrong model.
"""

from __future__ import annotations

import pytest

from harness.run import normalize_outcome


@pytest.mark.parametrize(
    ("conclusion", "expected"),
    [
        # Rehearsal 1, arm C: scored "rejected".
        (
            "Indeterminate. The campaign constitutes war crimes of intentionally directing "
            "attacks against the civilian population and indiscriminate attacks, but the "
            "specific crime of terror — which requires proof that the primary purpose of the "
            "violence was to spread terror among civilians — is not established on the facts "
            "provided.",
            "indeterminate",
        ),
        # Rehearsal 1, arm D: scored "indeterminate" because the first sentence says what
        # the campaign did constitute.
        (
            "No. The campaign constituted war crimes — specifically, intentionally directing "
            "attacks against the civilian population and indiscriminate attacks — but the "
            "specific crime of terror under Article 51(2) of Additional Protocol I requires "
            "proof that the primary purpose of the violence was to spread terror among the "
            "civilian population.",
            "rejected",
        ),
        # Rehearsal 2, arm D: the same answer, which the old parser happened to score right.
        (
            "No. The campaign of sniping and shelling constituted war crimes — including "
            "intentionally directing attacks against the civilian population and possibly "
            "indiscriminate attacks — but the specific crime of terror is not established on "
            "this record.",
            "rejected",
        ),
        # Run 3, arm C.
        (
            "Yes. The sustained campaign of sniping and shelling against the besieged city "
            "constituted the crime of terror against the civilian population as a violation "
            "of the laws and customs of war.",
            "affirmed",
        ),
        # "lawful" in an affirmative answer is not a denial.
        ("Yes. The shelling had no military purpose and was not lawful.", "affirmed"),
        (
            "Yes. Attacks on civilians, as opposed to lawful military objectives, are prohibited.",
            "affirmed",
        ),
        ("indeterminate. The record does not allow an answer.", "indeterminate"),
    ],
)
def test_real_conclusions_are_scored_by_their_opening_answer(
    conclusion: str, expected: str
) -> None:
    assert normalize_outcome(conclusion) == expected


def test_a_yes_that_denies_itself_is_still_indeterminate() -> None:
    """The conservative case the opener rule keeps."""
    assert normalize_outcome("Yes, the accused is not criminally responsible.") == ("indeterminate")
