"""The case schema's public face must never carry ground truth (ADR 0013)."""

from __future__ import annotations

from council_core.models.case import Case, Outcome, PublicCase

GROUND_TRUTH_FIELDS = {"holding", "outcome", "key_reasoning", "source_case_id"}


def _case(**overrides: object) -> Case:
    fields: dict[str, object] = {
        "id": "demo_case",
        "title": "Prosecutor v. Demo",
        "court": "ICTY",
        "year": 2003,
        "question": "Was the attack lawful?",
        "facts": "Shells landed on a market.",
        "holding": "SENTINEL-HOLDING the attack was unlawful.",
        "outcome": Outcome.AFFIRMED,
        "key_reasoning": ["SENTINEL-REASONING distinction"],
        "difficulty": "contested",
        "source_case_id": "SENTINEL-SOURCE",
    }
    fields.update(overrides)
    return Case.model_validate(fields)


def test_public_view_carries_no_ground_truth_field() -> None:
    public = _case().public().model_dump()

    assert GROUND_TRUTH_FIELDS.isdisjoint(public)
    assert set(public) == {"id", "title", "court", "year", "question", "facts", "difficulty"}


def test_ground_truth_values_do_not_appear_anywhere_in_the_serialised_view() -> None:
    serialised = _case().public().model_dump_json()

    assert "SENTINEL" not in serialised
    assert "affirmed" not in serialised


def test_public_view_keeps_what_the_picker_needs() -> None:
    public = _case().public()

    assert public.question == "Was the attack lawful?"
    assert public.facts == "Shells landed on a market."
    assert public.difficulty == "contested"


def test_a_field_added_to_case_is_not_public_unless_listed_on_purpose() -> None:
    # Every Case field is either public on purpose or ground truth on purpose.
    case_fields = set(Case.model_fields)
    public_fields = set(PublicCase.model_fields)

    assert public_fields <= case_fields
    assert case_fields - public_fields == GROUND_TRUTH_FIELDS
