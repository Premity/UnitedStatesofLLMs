"""Index bundles: one machine embeds, the others import (ADR 0014).

Every check here guards a failure that would otherwise be silent: vectors from
another embedding model, a half-finished embedding run, a corrupted transfer.
Qdrant is mocked over HTTP with respx; nothing touches the network.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import httpx
import pytest
import respx
from indexer.bundle import (
    INDEX_MEMBER,
    MANIFEST_MEMBER,
    BundleError,
    BundleManifest,
    Qdrant,
    Settings,
    _dotenv_value,
    export_bundle,
    import_bundle,
    read_manifest,
    status,
)

URL = "http://qdrant.test"
COLLECTION = "ihl_corpus"
MODEL = "BAAI/bge-large-en-v1.5"  # 1024 dimensions in fastembed's catalogue
SNAPSHOT_BYTES = b"pretend-qdrant-snapshot"
INDEX = {
    "version": "0.1.0",
    "instruments": ["ap_i"],
    "entries": {
        "ap_i/art.51": {"text": "Article 51.", "source_url": "u"},
        "ap_i/art.52": {"text": "Article 52.", "source_url": "u"},
    },
}


def _settings(tmp_path: Path, model: str = MODEL) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        qdrant_url=URL,
        collection=COLLECTION,
        embedding_model=model,
    )


def _write_index(settings: Settings, index: dict = INDEX) -> None:
    settings.index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.index_path.write_text(json.dumps(index), encoding="utf-8")


def _mock_qdrant(
    router: respx.MockRouter,
    *,
    points: int = 2,
    size: int = 1024,
    version: str = "1.12.4",
    after_upload: tuple[int, int] | None = None,
) -> dict[str, list]:
    """A Qdrant holding `points` points. Returns the calls made, by kind."""
    calls: dict[str, list] = {"uploaded": [], "deleted": []}
    state = {"points": points, "size": size}

    def collection(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"result": {"config": {"params": {"vectors": {"size": state["size"]}}}}}
        )

    def upload(request: httpx.Request) -> httpx.Response:
        calls["uploaded"].append(request.read())
        if after_upload is not None:
            state["points"], state["size"] = after_upload
        return httpx.Response(200, json={"result": True})

    def delete(request: httpx.Request) -> httpx.Response:
        calls["deleted"].append(request.url.path)
        return httpx.Response(200, json={"result": True})

    router.get(f"{URL}/").respond(200, json={"version": version})
    router.get(f"{URL}/collections/{COLLECTION}").mock(side_effect=collection)
    router.post(f"{URL}/collections/{COLLECTION}/points/count").mock(
        side_effect=lambda _r: httpx.Response(200, json={"result": {"count": state["points"]}})
    )
    router.post(f"{URL}/collections/{COLLECTION}/snapshots").respond(
        200, json={"result": {"name": "snap-1"}}
    )
    router.get(f"{URL}/collections/{COLLECTION}/snapshots/snap-1").respond(
        200, content=SNAPSHOT_BYTES
    )
    router.delete(f"{URL}/collections/{COLLECTION}/snapshots/snap-1").mock(side_effect=delete)
    router.post(f"{URL}/collections/{COLLECTION}/snapshots/upload").mock(side_effect=upload)
    return calls


def _qdrant() -> Qdrant:
    return Qdrant(URL, client=httpx.Client(base_url=URL))


def _export(tmp_path: Path, **qdrant_state) -> Path:
    settings = _settings(tmp_path / "builder")
    _write_index(settings)
    with respx.mock(assert_all_called=False) as router:
        calls = _mock_qdrant(router, **qdrant_state)
        bundle = export_bundle(settings, tmp_path / "out", qdrant=_qdrant())
    assert calls["deleted"], "the server-side snapshot must be cleaned up"
    return bundle


# ── Export ────────────────────────────────────────────────────────────────────


def test_export_packs_manifest_index_and_snapshot(tmp_path: Path) -> None:
    bundle = _export(tmp_path)

    manifest = read_manifest(bundle)
    assert manifest.embedding_model == MODEL
    assert (manifest.points, manifest.vector_size) == (2, 1024)
    assert manifest.qdrant_version == "1.12.4"
    assert manifest.corpus.locators == 2
    assert bundle.name == f"ihl-index-{manifest.corpus.short_hash}.tar"
    with tarfile.open(bundle) as tar:
        assert tar.extractfile("collection.snapshot").read() == SNAPSHOT_BYTES


def test_export_refuses_a_half_built_collection(tmp_path: Path) -> None:
    """The embedding run that OOM-killed the editor would leave exactly this."""
    settings = _settings(tmp_path)
    _write_index(settings)
    with (
        respx.mock(assert_all_called=False) as router,
        pytest.raises(BundleError, match="stopped partway"),
    ):
        _mock_qdrant(router, points=1)
        export_bundle(settings, tmp_path / "out", qdrant=_qdrant())


def test_export_refuses_vectors_of_another_models_width(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_index(settings)
    with (
        respx.mock(assert_all_called=False) as router,
        pytest.raises(BundleError, match="different model"),
    ):
        _mock_qdrant(router, size=384)
        export_bundle(settings, tmp_path / "out", qdrant=_qdrant())


def test_export_refuses_an_empty_citation_index(tmp_path: Path) -> None:
    with (
        respx.mock(assert_all_called=False) as router,
        pytest.raises(BundleError, match="missing or empty"),
    ):
        _mock_qdrant(router)
        export_bundle(_settings(tmp_path), tmp_path / "out", qdrant=_qdrant())


# ── Import ────────────────────────────────────────────────────────────────────


def test_import_restores_both_halves_and_records_the_bundle(tmp_path: Path) -> None:
    bundle = _export(tmp_path)
    settings = _settings(tmp_path / "importer")
    _write_index(settings, {"version": "0.1.0", "instruments": [], "entries": {}})

    with respx.mock(assert_all_called=False) as router:
        calls = _mock_qdrant(router, points=0, after_upload=(2, 1024))
        manifest = import_bundle(settings, bundle, qdrant=_qdrant())

    assert SNAPSHOT_BYTES in calls["uploaded"][0]
    assert json.loads(settings.index_path.read_text()) == INDEX
    assert settings.index_path.with_suffix(".json.bak").exists()
    assert BundleManifest.model_validate_json(settings.imported_record.read_text()) == manifest


def test_import_refuses_a_different_embedding_model_before_touching_anything(
    tmp_path: Path,
) -> None:
    bundle = _export(tmp_path)
    settings = _settings(tmp_path / "importer", model="BAAI/bge-small-en-v1.5")

    with respx.mock(assert_all_called=False) as router:
        calls = _mock_qdrant(router)
        with pytest.raises(BundleError, match="EMBEDDING_MODEL here is BAAI/bge-small"):
            import_bundle(settings, bundle, qdrant=_qdrant())

    assert calls["uploaded"] == []
    assert not settings.index_path.exists()


def test_import_refuses_a_different_qdrant_version(tmp_path: Path) -> None:
    bundle = _export(tmp_path)
    with respx.mock(assert_all_called=False) as router:
        calls = _mock_qdrant(router, version="1.13.0")
        with pytest.raises(BundleError, match="off the pin"):
            import_bundle(_settings(tmp_path / "importer"), bundle, qdrant=_qdrant())
    assert calls["uploaded"] == []


def test_import_refuses_a_citation_index_that_does_not_match_its_manifest(
    tmp_path: Path,
) -> None:
    """A truncated or edited transfer must not become this machine's index."""
    bundle = _export(tmp_path)
    tampered = tmp_path / "tampered.tar"
    with tarfile.open(bundle) as src, tarfile.open(tampered, "w") as dst:
        for member in src.getmembers():
            data = src.extractfile(member).read()
            if member.name == INDEX_MEMBER:
                index = json.loads(data)
                index["entries"].pop("ap_i/art.52")
                data = json.dumps(index).encode()
                member.size = len(data)
            dst.addfile(member, io.BytesIO(data))

    with respx.mock(assert_all_called=False) as router:
        calls = _mock_qdrant(router)
        with pytest.raises(BundleError, match="altered or truncated"):
            import_bundle(_settings(tmp_path / "importer"), tampered, qdrant=_qdrant())
    assert calls["uploaded"] == []


def test_import_keeps_the_old_index_if_the_restore_comes_out_wrong(tmp_path: Path) -> None:
    bundle = _export(tmp_path)
    settings = _settings(tmp_path / "importer")
    old = {"version": "0.1.0", "instruments": ["gc_i"], "entries": {"gc_i/art.3": {"text": "x"}}}
    _write_index(settings, old)

    with respx.mock(assert_all_called=False) as router:
        _mock_qdrant(router, after_upload=(1, 1024))
        with pytest.raises(BundleError, match="left unchanged"):
            import_bundle(settings, bundle, qdrant=_qdrant())

    assert json.loads(settings.index_path.read_text()) == old
    assert not settings.imported_record.exists()


def test_a_file_that_is_not_a_bundle_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "not-a-bundle.tar"
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo("readme.txt")
        tar.addfile(info, io.BytesIO(b""))
    with pytest.raises(BundleError, match=f"{MANIFEST_MEMBER} is missing"):
        read_manifest(path)


# ── Status ────────────────────────────────────────────────────────────────────


def test_status_is_clean_when_both_halves_agree(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_index(settings)
    with respx.mock(assert_all_called=False) as router:
        _mock_qdrant(router)
        lines, problems = status(settings, qdrant=_qdrant())

    assert problems == []
    assert lines[-1].startswith("Fingerprint: corpus ")
    assert f"model {MODEL} · 2 points · qdrant 1.12.4" in lines[-1]


def test_status_flags_points_that_do_not_match_locators(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_index(settings)
    with respx.mock(assert_all_called=False) as router:
        _mock_qdrant(router, points=1)
        _, problems = status(settings, qdrant=_qdrant())
    assert any("1 points but the citation index has 2" in p for p in problems)


def test_status_flags_an_index_changed_since_import(tmp_path: Path) -> None:
    bundle = _export(tmp_path)
    settings = _settings(tmp_path / "importer")
    with respx.mock(assert_all_called=False) as router:
        _mock_qdrant(router, after_upload=(2, 1024))
        import_bundle(settings, bundle, qdrant=_qdrant())
    _write_index(settings, {"version": "0.1.0", "instruments": ["ap_i"], "entries": {}})

    with respx.mock(assert_all_called=False) as router:
        _mock_qdrant(router)
        _, problems = status(settings, qdrant=_qdrant())
    assert any("changed since the bundle was imported" in p for p in problems)


def test_status_reports_an_unreachable_qdrant_as_a_problem(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _write_index(settings)
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{URL}/").mock(side_effect=httpx.ConnectError("refused"))
        lines, problems = status(settings, qdrant=_qdrant())
    assert any("not reachable" in p for p in problems)
    assert "qdrant unreachable" in lines[-1]


# ── Settings ──────────────────────────────────────────────────────────────────


def test_dotenv_is_read_the_way_compose_reads_it(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# EMBEDDING_MODEL=commented-out\n"
        "EMBEDDING_MODEL=BAAI/bge-small-en-v1.5  # inline comment\n"
        "EMPTY=\n"
    )
    assert _dotenv_value("EMBEDDING_MODEL", env) == "BAAI/bge-small-en-v1.5"
    assert _dotenv_value("EMPTY", env) is None
    assert _dotenv_value("MISSING", env) is None


def test_environment_beats_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("EMBEDDING_MODEL=from-dotenv\n")
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    assert Settings.from_environment(tmp_path).embedding_model == "from-dotenv"
    monkeypatch.setenv("EMBEDDING_MODEL", "from-env")
    assert Settings.from_environment(tmp_path).embedding_model == "from-env"
