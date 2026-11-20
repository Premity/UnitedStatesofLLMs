"""The evaluation's case scope (ADR 0012).

The scored run is three named cases; three more are a stretch tier run only with
judge quota left over. These tests pin that scope to the fixtures on disk, so a
renamed or deleted fixture fails here rather than silently shrinking a run.
"""

from __future__ import annotations

import pytest

from council_core.models.case import Outcome
from harness.cases import (
    CORE_CASE_IDS,
    EXTENDED_CASE_IDS,
    STRETCH_CASE_IDS,
    load_cases,
    select_cases,
)
from harness.run import build_parser


@pytest.fixture(scope="module")
def dev_cases():
    return load_cases(held_out=False)


def test_core_tier_is_the_three_scored_cases_in_order(dev_cases) -> None:
    selected = select_cases(dev_cases, tier="core")
    assert [case.id for case in selected] == list(CORE_CASE_IDS)
    assert len(selected) == 3


def test_core_tier_covers_both_outcomes(dev_cases) -> None:
    """A core set of only affirmed cases would reward a system that always says yes."""
    outcomes = {case.outcome for case in select_cases(dev_cases, tier="core")}
    assert {Outcome.AFFIRMED, Outcome.REJECTED} <= outcomes


def test_stretch_tier_follows_core_and_never_overlaps_it(dev_cases) -> None:
    stretch = select_cases(dev_cases, tier="stretch")
    assert [case.id for case in stretch] == list(STRETCH_CASE_IDS)
    assert not set(CORE_CASE_IDS) & set(STRETCH_CASE_IDS)
    everything = select_cases(dev_cases, tier="all")
    assert [case.id for case in everything] == list(
        CORE_CASE_IDS + STRETCH_CASE_IDS + EXTENDED_CASE_IDS
    )


def test_every_fixture_is_in_exactly_one_tier(dev_cases) -> None:
    """A fixture outside every tier can never be run; one in two would be run twice."""
    tiers = [CORE_CASE_IDS, STRETCH_CASE_IDS, EXTENDED_CASE_IDS]
    for case in dev_cases:
        assert sum(case.id in tier for tier in tiers) == 1, case.id
    assert len(select_cases(dev_cases, tier="all")) == len(dev_cases)


def test_extended_tier_covers_every_outcome(dev_cases) -> None:
    outcomes = {case.outcome for case in select_cases(dev_cases, tier="extended")}
    assert outcomes == set(Outcome)


def test_fictional_cases_say_so(dev_cases) -> None:
    """A `hyp_` case's ground truth is authored, not a tribunal's; the file must say so."""
    for case in dev_cases:
        fictional = case.id.startswith("hyp_")
        assert fictional == (case.court == "Hypothetical"), case.id
        if fictional:
            assert case.holding.startswith("Authored ground truth"), case.id
            assert case.source_case_id is None, case.id


def test_case_ids_narrow_a_tier_and_keep_its_order(dev_cases) -> None:
    selected = select_cases(
        dev_cases, tier="core", case_ids=["icc_bemba_command", "icty_galic_terror"]
    )
    assert [case.id for case in selected] == ["icty_galic_terror", "icc_bemba_command"]


def test_a_case_outside_the_tier_fails_loudly(dev_cases) -> None:
    with pytest.raises(ValueError, match="Not in tier 'core'"):
        select_cases(dev_cases, tier="core", case_ids=["icty_martic_zagreb"])


def test_a_tier_case_with_no_fixture_fails_loudly(dev_cases) -> None:
    without_galic = [case for case in dev_cases if case.id != "icty_galic_terror"]
    with pytest.raises(ValueError, match="No fixture for: icty_galic_terror"):
        select_cases(without_galic, tier="core")


def test_unknown_tier_is_rejected(dev_cases) -> None:
    with pytest.raises(ValueError, match="Unknown tier"):
        select_cases(dev_cases, tier="everything")


def test_cli_defaults_to_the_core_tier() -> None:
    args = build_parser().parse_args(["--all-arms", "--dry-run"])
    assert args.tier == "core"
    assert args.case_ids is None


def test_cli_accepts_repeated_case_flags() -> None:
    args = build_parser().parse_args(
        ["--all-arms", "--tier", "stretch", "--case", "icty_martic_zagreb", "--case", "x"]
    )
    assert args.tier == "stretch"
    assert args.case_ids == ["icty_martic_zagreb", "x"]
