"""The manifest is the corpus scope, so a mistake here is a silent coverage gap.

Corpus ids are written into every stored run artifact and are therefore
permanent (ADR 0007). These tests pin the decisions in ADR 0010 so the manifest
cannot drift away from them unnoticed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parents[3] / "corpus" / "manifests" / "treaties.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(manifest: dict) -> dict:
    return {i["id"]: i for i in manifest["instruments"]}


def test_every_instrument_has_what_the_fetcher_needs(manifest: dict) -> None:
    for inst in manifest["instruments"]:
        for key in ("id", "title", "year", "source_url", "icrc_node", "path", "status"):
            assert key in inst, f"{inst.get('id')} is missing {key!r}"


def test_corpus_ids_are_unique_and_slugs(manifest: dict) -> None:
    """Ids are permanent and are the first half of every locator."""
    ids = [i["id"] for i in manifest["instruments"]]
    assert len(ids) == len(set(ids))
    for i in ids:
        assert re.fullmatch(r"[a-z0-9_]+", i), i


def test_hague_regulations_are_a_separate_corpus_id(by_id: dict) -> None:
    """The Regulations renumber from 1, so a single id would make
    `hague_iv/art.3` ambiguous between two different provisions -- and the
    resolver would return whichever the index happened to hold. ADR 0010."""
    assert "hague_iv" in by_id
    assert "hague_iv_regs" in by_id
    assert by_id["hague_iv"]["icrc_section"] == "Article"
    assert by_id["hague_iv_regs"]["icrc_section"] == "Annex"


def test_the_two_hague_documents_come_from_one_source(by_id: dict) -> None:
    """Two corpus ids, one treaty: they are sections of the same ICRC node."""
    assert by_id["hague_iv"]["icrc_node"] == by_id["hague_iv_regs"]["icrc_node"]


def test_rome_amendments_declare_how_they_merge(by_id: dict) -> None:
    """Each amendment has a different shape, so each needs a stated rule.
    An unhandled shape would silently drop 8(2)(e)(xiii)-(xv). ADR 0010."""
    amendments = by_id["rome_statute"]["amendments"]
    assert {a["merge"] for a in amendments} == {
        "replace_article",
        "add_articles",
        "delete_article",
    }
    for a in amendments:
        assert a["affects"], f"{a['id']} does not say which articles it touches"
        assert a["icrc_node"]


def test_unindexed_rome_amendments_record_why(by_id: dict) -> None:
    """A guessed locator is indistinguishable from a fabrication, so these are
    omitted deliberately -- and the omission has to stay visible."""
    gaps = by_id["rome_statute"]["not_indexed"]
    assert len(gaps) == 3
    for gap in gaps:
        assert gap["reason"]
        assert gap["icrc_node"]


CORE_INSTRUMENTS = {
    "gc_i",
    "gc_ii",
    "gc_iii",
    "gc_iv",
    "ap_i",
    "ap_ii",
    "rome_statute",
    "hague_iv",
    "hague_iv_regs",
}


def test_the_core_instruments_are_all_present(by_id: dict) -> None:
    """The set the evaluation fixtures actually turn on."""
    assert set(by_id) >= CORE_INSTRUMENTS


def test_every_ccw_protocol_is_its_own_corpus_id(by_id: dict) -> None:
    """Each protocol numbers its articles from 1, so one shared id would make
    `ccw/art.2` ambiguous across five documents -- the Hague IV problem again
    (ADR 0010)."""
    for protocol in ("ccw_p_ii", "ccw_p_iii", "ccw_p_iv", "ccw_p_v"):
        assert protocol in by_id
        assert by_id[protocol]["icrc_node"] != by_id["ccw"]["icrc_node"]


def test_each_instrument_has_a_distinct_source_node(manifest: dict) -> None:
    """Two ids on one node is how Hague IV works, and only Hague IV: anywhere
    else it means a copy-pasted uuid, which would index the wrong treaty."""
    from collections import Counter

    shared = [
        node
        for node, count in Counter(i["icrc_node"] for i in manifest["instruments"]).items()
        if count > 1
    ]
    hague = {i["icrc_node"] for i in manifest["instruments"] if i["id"].startswith("hague_iv")}
    assert set(shared) <= hague
