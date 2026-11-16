"""The scored run's settings are frozen, and a machine that differs cannot join it.

The run may be split across machines; their results pool only if every one ran
the same roster, prompts, embedding model and citation index. Each differs
silently between machines, so a live run checks before it spends quota.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from council_core.citations.resolver import corpus_identity
from council_core.models.case import Case, Outcome
from harness.arms import ARMS
from harness.quota import QuotaTracker
from harness.run import run_evaluation
from harness.settings import (
    SettingsMismatchError,
    differences,
    fingerprint,
    require_frozen_settings,
)

FROZEN = {
    "roster": {
        "presenter": "groq/openai/gpt-oss-120b",
        "attacker_doctrinal": "groq/qwen/qwen3.8-27b",
        "attacker_evidentiary": "groq/openai/gpt-oss-20b",
        "judge": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    },
    "prompts": "f8a652539767" + "0" * 52,
    "embedding_model": "BAAI/bge-large-en-v1.5",
    "corpus": "8ffefb5a30ab" + "0" * 52,
}


def _with(**changes) -> dict:
    settings = json.loads(json.dumps(FROZEN))
    for key, value in changes.items():
        if key in FROZEN["roster"]:
            settings["roster"][key] = value
        else:
            settings[key] = value
    return settings


def _write_frozen(tmp_path: Path) -> Path:
    path = tmp_path / "frozen-settings.json"
    path.write_text(json.dumps({**FROZEN, "recorded_at": "2026-11-16T00:00:00+00:00"}))
    return path


def test_identical_settings_have_no_differences() -> None:
    assert differences(FROZEN, FROZEN) == []


@pytest.mark.parametrize(
    ("changes", "named"),
    [
        ({"judge": "openrouter/other:free"}, "judge model"),
        ({"prompts": "deadbeef" * 8}, "prompt set"),
        ({"embedding_model": "BAAI/bge-small-en-v1.5"}, "EMBEDDING_MODEL"),
        ({"corpus": "eb098296223e" + "0" * 52}, "citation index"),
    ],
)
def test_each_kind_of_difference_is_named(changes: dict, named: str) -> None:
    found = differences(_with(**changes), FROZEN)
    assert len(found) == 1
    assert named in found[0]


def test_the_fingerprint_covers_only_compared_settings() -> None:
    assert fingerprint({**FROZEN, "recorded_at": "x"}) == fingerprint(FROZEN)
    assert fingerprint(_with(judge="other")) != fingerprint(FROZEN)


def test_nothing_frozen_means_nothing_to_check(tmp_path: Path) -> None:
    require_frozen_settings(_with(judge="other"), path=tmp_path / "absent.json")


def test_a_mismatch_is_refused_with_every_difference(tmp_path: Path) -> None:
    path = _write_frozen(tmp_path)
    with pytest.raises(SettingsMismatchError) as raised:
        require_frozen_settings(_with(judge="x", prompts="y" * 64), path=path)
    assert "judge model" in str(raised.value)
    assert "prompt set" in str(raised.value)
    assert "--allow-unfrozen-settings" in str(raised.value)


def test_matching_settings_pass(tmp_path: Path) -> None:
    require_frozen_settings(FROZEN, path=_write_frozen(tmp_path))


# ── Through the harness ───────────────────────────────────────────────────────


@pytest.fixture
def case() -> Case:
    return Case(
        id="case_1",
        title="Case 1",
        court="ICTY",
        year=2003,
        question="Q?",
        facts="F.",
        holding="H.",
        outcome=Outcome.AFFIRMED,
        key_reasoning=["k"],
        difficulty="medium",
    )


@pytest.fixture
def populated_resolver():
    resolver = MagicMock()
    resolver.corpus_identity.return_value = corpus_identity(
        {"ap_i/art.51": {"text": "."}}, ["ap_i"]
    )
    with patch("harness.run.get_resolver", return_value=resolver):
        yield


@pytest.mark.asyncio
async def test_a_live_run_on_unfrozen_settings_refuses_before_writing(
    tmp_path: Path, case: Case, populated_resolver
) -> None:
    out = tmp_path / "out"
    graph = AsyncMock(side_effect=AssertionError("ran on unfrozen settings"))
    with (
        patch("harness.settings.FROZEN_PATH", _write_frozen(tmp_path)),
        patch("harness.settings.current_settings", return_value=_with(judge="x")),
        patch("harness.run.compiled_graph.ainvoke", graph),
        pytest.raises(SettingsMismatchError),
    ):
        await run_evaluation(
            arms=[ARMS["raw"]],
            cases=[case],
            judge_backend="api",
            output_dir=out,
            quota_tracker=QuotaTracker(tmp_path / "quota_log.json"),
            auto_go=True,
        )
    assert not out.exists()


@pytest.mark.asyncio
async def test_the_override_runs_and_records_the_embedding_model(
    tmp_path: Path, case: Case, populated_resolver
) -> None:
    final_state = {
        "current_round": 1,
        "turns": [],
        "arguments": [],
        "objections": [],
        "context": [],
        "verdict": None,
    }
    with (
        patch("harness.settings.FROZEN_PATH", _write_frozen(tmp_path)),
        patch("harness.settings.current_settings", return_value=_with(judge="x")),
        patch("harness.run.compiled_graph.ainvoke", AsyncMock(return_value=final_state)),
    ):
        results = await run_evaluation(
            arms=[ARMS["raw"]],
            cases=[case],
            judge_backend="local",
            output_dir=tmp_path / "out",
            quota_tracker=QuotaTracker(tmp_path / "quota_log.json"),
            auto_go=True,
            allow_unfrozen_settings=True,
        )
    assert results[0]["status"] == "completed"
    assert results[0]["embedding_model"]
