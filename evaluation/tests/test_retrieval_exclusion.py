"""Evaluation cases pass source-case exclusions into the debate graph."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from council_core.models.case import Case, Outcome
from harness.arms import ARMS
from harness.quota import QuotaTracker
from harness.run import run_case


@pytest.mark.asyncio
async def test_source_case_id_is_passed_to_graph_retrieval(tmp_path: Path) -> None:
    case = Case(
        id="case_under_test",
        title="Case under test",
        court="ICTY",
        year=2003,
        question="Question",
        facts="Facts",
        holding="Holding",
        outcome=Outcome.AFFIRMED,
        source_case_id="icty_galic_tj",
    )
    graph_call = AsyncMock(
        return_value={
            "current_round": 1,
            "turns": [],
            "arguments": [],
            "objections": [],
            "context": [],
            "verdict": None,
        }
    )

    with patch("harness.run.compiled_graph.ainvoke", graph_call):
        await run_case(
            ARMS["rag"],
            case,
            judge_backend="api",
            output_dir=tmp_path,
            quota_tracker=QuotaTracker(tmp_path / "quota.json"),
        )

    initial_state = graph_call.call_args.args[0]
    assert initial_state["excluded_case_id"] == "icty_galic_tj"
