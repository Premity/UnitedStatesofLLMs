"""The case picker's endpoints must never serve ground truth (ADR 0013)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

GROUND_TRUTH_KEYS = {"holding", "outcome", "key_reasoning", "source_case_id"}
SENTINELS = ("SENTINEL-HOLDING", "SENTINEL-REASONING", "SENTINEL-SOURCE")

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_case(directory: Path, case_id: str, **extra: object) -> None:
    case = {
        "id": case_id,
        "title": "Prosecutor v. Demo",
        "court": "ICTY",
        "year": 2003,
        "question": "Was the attack lawful?",
        "facts": "Shells landed on a market.",
        "holding": "SENTINEL-HOLDING the attack was unlawful.",
        "outcome": "affirmed",
        "key_reasoning": ["SENTINEL-REASONING distinction"],
        "difficulty": "contested",
        "source_case_id": "SENTINEL-SOURCE",
        **extra,
    }
    (directory / f"{case_id}.json").write_text(json.dumps(case), encoding="utf-8")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _write_case(tmp_path, "demo_one")
    _write_case(tmp_path, "demo_two", extra_ground_truth_added_later="SENTINEL-FUTURE")
    monkeypatch.setattr("app.routers.cases.get_settings", lambda: Settings(cases_dir=tmp_path))
    return TestClient(app)


def test_list_returns_public_fields_only(client: TestClient) -> None:
    response = client.get("/cases")

    assert response.status_code == 200
    body = response.json()
    assert [c["id"] for c in body] == ["demo_one", "demo_two"]
    for case in body:
        assert GROUND_TRUTH_KEYS.isdisjoint(case)
        assert set(case) == {"id", "title", "court", "year", "question", "facts", "difficulty"}


def test_no_ground_truth_value_appears_anywhere_in_either_response(client: TestClient) -> None:
    texts = [client.get("/cases").text, client.get("/cases/demo_one").text]

    for text in texts:
        for sentinel in SENTINELS:
            assert sentinel not in text
        assert "SENTINEL-FUTURE" not in text
        assert "affirmed" not in text


def test_get_one_returns_question_and_facts(client: TestClient) -> None:
    body = client.get("/cases/demo_one").json()

    assert body["question"] == "Was the attack lawful?"
    assert body["facts"] == "Shells landed on a market."


def test_unknown_case_is_404(client: TestClient) -> None:
    assert client.get("/cases/nope").status_code == 404


def test_a_missing_directory_serves_an_empty_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.routers.cases.get_settings", lambda: Settings(cases_dir=tmp_path / "absent")
    )

    assert TestClient(app).get("/cases").json() == []


def test_an_unparseable_file_is_skipped_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_case(tmp_path, "good")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("app.routers.cases.get_settings", lambda: Settings(cases_dir=tmp_path))

    assert [c["id"] for c in TestClient(app).get("/cases").json()] == ["good"]


def test_the_shipped_dev_cases_leak_nothing() -> None:
    dev = REPO_ROOT / "evaluation" / "cases" / "dev"
    shipped = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(dev.glob("*.json"))]
    assert shipped, "no dev cases found"

    from app.routers.cases import load_public_cases

    served = [c.model_dump() for c in load_public_cases(dev)]

    assert len(served) == len(shipped)
    for original, public in zip(shipped, served, strict=True):
        assert GROUND_TRUTH_KEYS.isdisjoint(public)
        # The holding is long prose; none of it may appear in what is served.
        assert original["holding"] not in json.dumps(public)
