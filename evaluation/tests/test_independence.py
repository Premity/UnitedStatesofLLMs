"""Tests for attacker independence metrics (T2-3).

Verifies that:
1. `jaccard` token similarity matches expected values on identical (1.0),
   disjoint (0.0), and partial (e.g. 0.5) token sets.
2. `_tokens` extracts content words while properly stripping legal domain stopwords.
3. `measure_independence` accurately computes token Jaccard and target argument overlap
   for identical, disjoint, and partially overlapping objection sets.
4. Edge cases (empty objections, single-attacker-only runs) are handled cleanly.
"""

from __future__ import annotations

import pytest

from council_core.models.debate import Objection, Role
from metrics.independence import IndependenceResult, _tokens, jaccard, measure_independence


class TestJaccardFunction:
    """Direct tests for the Jaccard similarity function."""

    def test_identical_sets(self) -> None:
        assert (
            jaccard({"proportionality", "distinction"}, {"proportionality", "distinction"}) == 1.0
        )

    def test_disjoint_sets(self) -> None:
        assert jaccard({"proportionality", "distinction"}, {"radar", "telemetry"}) == 0.0

    def test_partial_overlap(self) -> None:
        set_a = {"collateral", "civilian", "excessive"}
        set_b = {"civilian", "excessive", "forensic"}
        # Intersection: {"civilian", "excessive"} -> 2
        # Union: {"collateral", "civilian", "excessive", "forensic"} -> 4
        # Jaccard: 2 / 4 = 0.5
        assert jaccard(set_a, set_b) == 0.5

    def test_empty_sets(self) -> None:
        assert jaccard(set(), set()) == 0.0
        assert jaccard({"proportionality"}, set()) == 0.0
        assert jaccard(set(), {"distinction"}) == 0.0


class TestTokenExtraction:
    """Tests token extraction and legal stopword filtering."""

    def test_strips_punctuation_and_lowercases(self) -> None:
        tokens = _tokens("Civilian, 'collateral' (damage) [assessment].")
        assert tokens == {"civilian", "collateral", "damage", "assessment"}

    def test_filters_domain_stopwords(self) -> None:
        # Stopwords: the, argument, fails, because, therefore, objection, however, is, that
        text = "The argument fails because this objection is that therefore however"
        tokens = _tokens(text)
        assert len(tokens) == 0


class TestMeasureIndependence:
    """Tests for measure_independence over Objection sets."""

    def test_identical_objection_sets(self) -> None:
        """When both attackers raise identical grounds against the same target argument.

        Jaccard = 1.0, target_overlap = 1.0.
        """
        ground_text = "Civilian casualties exceed expected concrete military advantage."
        objections = [
            Objection(
                raised_by=Role.ATTACKER_DOCTRINAL,
                target_argument_id="arg_1",
                ground=ground_text,
                reasoning="Doctrinal analysis.",
            ),
            Objection(
                raised_by=Role.ATTACKER_EVIDENTIARY,
                target_argument_id="arg_1",
                ground=ground_text,
                reasoning="Evidentiary analysis.",
            ),
        ]

        result = measure_independence(objections)

        assert isinstance(result, IndependenceResult)
        assert result.jaccard == 1.0
        assert result.target_overlap == 1.0
        assert result.doctrinal_count == 1
        assert result.evidentiary_count == 1

    def test_disjoint_objection_sets(self) -> None:
        """When attackers raise completely distinct grounds against different target arguments.

        Jaccard = 0.0, target_overlap = 0.0.
        """
        objections = [
            Objection(
                raised_by=Role.ATTACKER_DOCTRINAL,
                target_argument_id="arg_doctrinal",
                ground="Proportionality calculation omitted anticipated civilian shelter destruction.",
                reasoning="Legal test failed.",
            ),
            Objection(
                raised_by=Role.ATTACKER_EVIDENTIARY,
                target_argument_id="arg_evidentiary",
                ground="Telemetry radar logs refute missile trajectory assertions.",
                reasoning="Factual predicate unsupported.",
            ),
        ]

        result = measure_independence(objections)

        # Doctrinal tokens: proportionality, calculation, omitted, anticipated, civilian, shelter, destruction
        # Evidentiary tokens: telemetry, radar, logs, refute, missile, trajectory, assertions
        # Disjoint grounds and distinct target arguments
        assert result.jaccard == 0.0
        assert result.target_overlap == 0.0
        assert result.doctrinal_count == 1
        assert result.evidentiary_count == 1

    def test_partial_overlap_objection_sets(self) -> None:
        """Partial overlap in vocabulary and shared targets.

        Doctrinal:
          target: arg_1
          ground: 'Excessive civilian casualties violate distinction principle'
          tokens: {excessive, civilian, casualties, violate, distinction, principle} (6 tokens)

        Evidentiary:
          targets: arg_1, arg_2
          ground: 'Civilian casualties unconfirmed by forensic hospital records'
          tokens: {civilian, casualties, unconfirmed, forensic, hospital, records} (6 tokens)

        Overlap:
          Intersection tokens: {civilian, casualties} (2)
          Union tokens: 6 + 6 - 2 = 10
          Expected Jaccard: 2 / 10 = 0.20

          Doctrinal targets: {arg_1}
          Evidentiary targets: {arg_1, arg_2}
          Target intersection: {arg_1} (1)
          Target union: {arg_1, arg_2} (2)
          Expected target_overlap: 1 / 2 = 0.50
        """
        objections = [
            Objection(
                raised_by=Role.ATTACKER_DOCTRINAL,
                target_argument_id="arg_1",
                ground="Excessive civilian casualties violate distinction principle.",
                reasoning="Reasoning A",
            ),
            Objection(
                raised_by=Role.ATTACKER_EVIDENTIARY,
                target_argument_id="arg_1",
                ground="Civilian casualties unconfirmed by forensic hospital records.",
                reasoning="Reasoning B1",
            ),
            Objection(
                raised_by=Role.ATTACKER_EVIDENTIARY,
                target_argument_id="arg_2",
                ground="Forensic hospital records contradict munitions claims.",
                reasoning="Reasoning B2",
            ),
        ]

        # Evidentiary grounds combined:
        # civilian casualties unconfirmed by forensic hospital records contradict munitions claims
        # Note 'claim' is a stopword, but 'claims' is retained.
        # Evidentiary tokens: civilian, casualties, unconfirmed, forensic, hospital, records, contradict, munitions, claims (9 tokens)
        # Doctrinal tokens: excessive, civilian, casualties, violate, distinction, principle (6 tokens)
        # Intersection: {civilian, casualties} (2 tokens)
        # Union: 6 + 9 - 2 = 13 tokens
        # Jaccard: 2 / 13
        result = measure_independence(objections)

        assert pytest.approx(result.jaccard, abs=1e-6) == 2.0 / 13.0
        assert pytest.approx(result.target_overlap, abs=1e-6) == 0.50
        assert result.doctrinal_count == 1
        assert result.evidentiary_count == 2

    def test_stopwords_do_not_produce_artificial_overlap(self) -> None:
        """Shared stopwords should not inflate Jaccard above 0."""
        objections = [
            Objection(
                raised_by=Role.ATTACKER_DOCTRINAL,
                target_argument_id="arg_1",
                ground="The argument fails because distinction requires careful analysis.",
                reasoning="Reasoning",
            ),
            Objection(
                raised_by=Role.ATTACKER_EVIDENTIARY,
                target_argument_id="arg_2",
                ground="The argument fails because munitions logs are missing.",
                reasoning="Reasoning",
            ),
        ]

        # 'the', 'argument', 'fails', 'because' are stopwords.
        # Doctrinal content: distinction, requires, careful, analysis (4)
        # Evidentiary content: munitions, logs, missing (3)
        # Intersection: empty -> Jaccard must be 0.0!
        result = measure_independence(objections)

        assert result.jaccard == 0.0
        assert result.target_overlap == 0.0

    def test_edge_cases_empty_or_single_attacker(self) -> None:
        """Handles empty objections list and runs with only one active attacker."""
        empty_res = measure_independence([])
        assert empty_res.jaccard == 0.0
        assert empty_res.target_overlap == 0.0
        assert empty_res.doctrinal_count == 0
        assert empty_res.evidentiary_count == 0

        only_doc = measure_independence(
            [
                Objection(
                    raised_by=Role.ATTACKER_DOCTRINAL,
                    target_argument_id="arg_1",
                    ground="Command responsibility doctrine misapplied.",
                    reasoning="Reasoning",
                )
            ]
        )
        assert only_doc.jaccard == 0.0
        assert only_doc.target_overlap == 0.0
        assert only_doc.doctrinal_count == 1
        assert only_doc.evidentiary_count == 0

        only_ev = measure_independence(
            [
                Objection(
                    raised_by=Role.ATTACKER_EVIDENTIARY,
                    target_argument_id="arg_1",
                    ground="Missing chain of custody for debris.",
                    reasoning="Reasoning",
                )
            ]
        )
        assert only_ev.jaccard == 0.0
        assert only_ev.target_overlap == 0.0
        assert only_ev.doctrinal_count == 0
        assert only_ev.evidentiary_count == 1
