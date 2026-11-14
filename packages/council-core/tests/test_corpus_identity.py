"""Which citation index scored a run (GitHub #24).

A citation status means something only against a known index, and each machine
resolves against whatever it last fetched (ADR 0007). The index's hand-set
`version` stayed "0.1.0" while it grew from 9 instruments to 23, so identity is
computed from the content.
"""

from __future__ import annotations

import json
from pathlib import Path

from council_core.citations.resolver import CitationResolver, JsonCorpusIndex, corpus_identity
from council_core.export.renderer import render_markdown
from council_core.models.corpus import CorpusIdentity
from council_core.models.debate import DebateConfig, DebateState, Verdict
from council_core.models.run import RunArtifact, RunMetadata

ENTRIES = {
    "ap_i/art.51": {"text": "The civilian population ... shall not be the object of attack."},
    "ap_i/art.57": {"text": "In the conduct of military operations, constant care ..."},
}


def _write_index(path: Path, *, entries: dict, instruments: list[str], version: str) -> Path:
    path.write_text(
        json.dumps({"version": version, "instruments": instruments, "entries": entries}),
        encoding="utf-8",
    )
    return path


def test_identity_counts_and_hashes_the_index(tmp_path: Path) -> None:
    index = JsonCorpusIndex(
        _write_index(tmp_path / "i.json", entries=ENTRIES, instruments=["ap_i"], version="0.1.0")
    )

    identity = index.identity()

    assert (identity.instruments, identity.locators) == (1, 2)
    assert len(identity.content_hash) == 64


def test_the_hand_set_version_does_not_decide_identity(tmp_path: Path) -> None:
    """The failure this exists for: same version string, different index."""
    small = JsonCorpusIndex(
        _write_index(tmp_path / "a.json", entries=ENTRIES, instruments=["ap_i"], version="0.1.0")
    )
    larger = JsonCorpusIndex(
        _write_index(
            tmp_path / "b.json",
            entries={**ENTRIES, "gc_iv/art.3": {"text": "..."}},
            instruments=["ap_i", "gc_iv"],
            version="0.1.0",
        )
    )
    relabelled = JsonCorpusIndex(
        _write_index(tmp_path / "c.json", entries=ENTRIES, instruments=["ap_i"], version="9.9.9")
    )

    assert small.identity().content_hash != larger.identity().content_hash
    assert small.identity() == relabelled.identity()


def test_identity_does_not_depend_on_how_the_file_was_written() -> None:
    reordered = dict(reversed(list(ENTRIES.items())))
    assert corpus_identity(ENTRIES, ["b", "a"]) == corpus_identity(reordered, {"a", "b"})


def test_a_missing_index_has_an_identity_of_its_own(tmp_path: Path) -> None:
    """Scored against nothing is a fact, distinct from not recorded."""
    identity = JsonCorpusIndex(tmp_path / "absent.json").identity()

    assert (identity.instruments, identity.locators) == (0, 0)
    assert identity == corpus_identity({}, [])


def test_the_resolver_reports_its_index_and_a_test_double_reports_none(tmp_path: Path) -> None:
    path = _write_index(tmp_path / "i.json", entries=ENTRIES, instruments=["ap_i"], version="x")
    assert CitationResolver(JsonCorpusIndex(path)).corpus_identity() == corpus_identity(
        ENTRIES, ["ap_i"]
    )

    class Fake:
        def lookup(self, locator: str) -> None:
            return None

        def knows_instrument(self, instrument: str) -> bool:
            return False

    assert CitationResolver(Fake()).corpus_identity() is None


def _artifact(corpus: CorpusIdentity | None) -> RunArtifact:
    return RunArtifact(
        metadata=RunMetadata(run_id="run_test", corpus=corpus),
        state=DebateState(
            config=DebateConfig(question="Was the attack lawful?"),
            verdict=Verdict(
                conclusion="It was not.",
                reasoning="The surviving arguments support it.",
                confidence=0.6,
                confidence_reasoning="Contested.",
                surviving_argument_ids=[],
                dissent=[],
            ),
        ),
    )


def test_an_artifact_round_trips_its_corpus() -> None:
    identity = corpus_identity(ENTRIES, ["ap_i"])
    loaded = RunArtifact.from_json(_artifact(identity).to_json())
    assert loaded.metadata.corpus == identity


def test_a_stored_artifact_without_a_corpus_still_loads_as_not_recorded() -> None:
    raw = json.loads(_artifact(None).to_json())
    del raw["metadata"]["corpus"]

    loaded = RunArtifact.from_json(json.dumps(raw))

    assert loaded.metadata.corpus is None
    assert "Corpus `not recorded`" in render_markdown(loaded)


def test_the_dissent_log_names_the_index() -> None:
    identity = corpus_identity(ENTRIES, ["ap_i"])
    rendered = render_markdown(_artifact(identity))
    assert f"Corpus `{identity.short_hash} (1 instruments, 2 locators)`" in rendered
