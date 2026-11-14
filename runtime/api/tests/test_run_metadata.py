"""The API records which citation index a run is scored against (GitHub #24)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.routers.debate import _initial_metadata
from council_core.citations.resolver import corpus_identity


def test_a_new_run_records_the_index_its_citations_resolve_against() -> None:
    identity = corpus_identity({"ap_i/art.51": {"text": "..."}}, ["ap_i"])
    resolver = MagicMock()
    resolver.corpus_identity.return_value = identity

    with patch("app.routers.debate.get_resolver", return_value=resolver):
        metadata = _initial_metadata("run_test")

    assert metadata.corpus == identity
