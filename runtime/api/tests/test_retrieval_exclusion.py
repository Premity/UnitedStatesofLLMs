"""Tests that evaluation retrieval excludes the case being evaluated."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.retrieval import RetrievalService, StubRetrievalService


@pytest.mark.asyncio
async def test_qdrant_search_filters_and_discards_the_source_case() -> None:
    service = RetrievalService.__new__(RetrievalService)
    service._collection = "ihl_corpus"
    service.embed = AsyncMock(return_value=[0.1, 0.2])
    service._client = AsyncMock()
    service._client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "case_id": "icty_galic_tj",
                    "citation_type": "case",
                    "instrument": "icty_galic_tj",
                    "paragraph": "58",
                    "text": "The source holding.",
                }
            ),
            SimpleNamespace(
                payload={
                    "case_id": "other_case",
                    "citation_type": "case",
                    "instrument": "other_case",
                    "paragraph": "12",
                    "text": "Another judgment.",
                }
            ),
        ]
    )

    spans = await service.search("the facts", excluded_case_id="icty_galic_tj")

    assert len(spans) == 1
    assert spans[0].citation.case_id == "other_case"
    query_filter = service._client.query_points.call_args.kwargs["query_filter"]
    assert query_filter.must_not[0].key == "case_id"
    assert query_filter.must_not[0].match.value == "icty_galic_tj"


@pytest.mark.asyncio
async def test_stub_search_skips_source_case_locators() -> None:
    service = StubRetrievalService.__new__(StubRetrievalService)
    service._path = Path("test-index.json")
    service._entries = lambda: {
        "icty_galic_tj/para.58": {"text": "The source holding."},
        "other_case/para.12": {"text": "Another judgment."},
        "ap_i/art.51(2)": {"text": "Treaty provision."},
    }

    spans = await service.search("holding provision", excluded_case_id="icty_galic_tj")

    locators = {span.citation.locator() for span in spans}
    assert "icty_galic_tj/para.58" not in locators
    assert "other_case/para.12" in locators
    assert "ap_i/art.51(2)" in locators
