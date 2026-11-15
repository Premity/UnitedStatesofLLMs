"""Share a built index between machines: export it, import it, check it.

The embedding stage is the expensive one; on a 16GB laptop it has taken the
editor down with it. So one machine builds the index and the others import it
(ADR 0014). A bundle is one tar file holding:

- ``bundle.json``: the settings it was built with (`BundleManifest`);
- ``citation_index.json``: what the citation resolver reads;
- ``collection.snapshot``: the Qdrant collection retrieval searches.

Both halves travel together because they must come from the same build: the
citation index decides what counts as fabrication, the collection decides what
retrieval can find, and a mismatched pair is wrong with no error.

Every check here guards a failure that is otherwise silent:

- a different ``EMBEDDING_MODEL`` gives meaningless similarity scores
  (non-negotiable #3);
- an embedding run killed partway leaves fewer points than locators;
- a different Qdrant version may not restore the snapshot.

    python -m indexer.bundle export [--out data/bundles]
    python -m indexer.bundle import data/bundles/ihl-index-<hash>.tar
    python -m indexer.bundle status

Runs on the host against the dev stack's Qdrant (``make up`` exposes 6333).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

import httpx
from pydantic import BaseModel

from council_core.citations.resolver import JsonCorpusIndex, corpus_identity
from council_core.models.corpus import CorpusIdentity
from council_core.telemetry import configure_logging

FORMAT_VERSION = 1
MANIFEST_MEMBER = "bundle.json"
INDEX_MEMBER = "citation_index.json"
SNAPSHOT_MEMBER = "collection.snapshot"

#: Written beside the citation index on import, so `status` can tell whether
#: this machine still holds what it imported.
IMPORTED_RECORD = "bundle.json"

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
DEFAULT_COLLECTION = "ihl_corpus"
DEFAULT_QDRANT_URL = "http://localhost:6333"


class BundleError(RuntimeError):
    """The bundle cannot be made or used safely. The message says why and what to do."""


class BundleManifest(BaseModel):
    """What a bundle was built with. Import refuses a bundle these do not match."""

    format_version: int
    created_at: datetime
    source_commit: str | None
    collection: str
    embedding_model: str
    vector_size: int
    points: int
    qdrant_version: str
    corpus: CorpusIdentity

    def describe(self) -> str:
        return fingerprint(self.corpus, self.embedding_model, self.points, self.qdrant_version)


def fingerprint(corpus: CorpusIdentity, model: str, points: int | None, qdrant: str) -> str:
    """One line two people can compare to know they hold the same index."""
    shown = "?" if points is None else str(points)
    return f"corpus {corpus.describe()} · model {model} · {shown} points · qdrant {qdrant}"


# ── Settings ──────────────────────────────────────────────────────────────────


def _dotenv_value(key: str, path: Path) -> str | None:
    """A value from `.env`, the way compose reads it: KEY=value, # comments."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == key and not name.lstrip().startswith("#"):
            value = value.split(" #", 1)[0].strip().strip("'\"")
            return value or None
    return None


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    qdrant_url: str
    collection: str
    embedding_model: str

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index" / "citation_index.json"

    @property
    def imported_record(self) -> Path:
        return self.data_dir / "index" / IMPORTED_RECORD

    @classmethod
    def from_environment(cls, repo_root: Path = REPO_ROOT) -> Settings:
        """Resolve each setting as the API container does: environment, then `.env`.

        The API gets `EMBEDDING_MODEL` from compose, which reads `.env`, so a
        value set only there still counts.
        """
        dotenv = repo_root / ".env"

        def setting(key: str, default: str) -> str:
            return os.environ.get(key) or _dotenv_value(key, dotenv) or default

        return cls(
            data_dir=Path(os.environ.get("DATA_DIR") or repo_root / "data"),
            qdrant_url=setting("QDRANT_URL", DEFAULT_QDRANT_URL),
            collection=setting("QDRANT_COLLECTION", DEFAULT_COLLECTION),
            embedding_model=setting("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        )


def model_dimensions(model: str) -> int | None:
    """The model's vector width from fastembed's catalogue, without loading it."""
    from fastembed import TextEmbedding

    for entry in TextEmbedding.list_supported_models():
        if entry.get("model") == model:
            return int(entry["dim"])
    return None


# ── Qdrant over HTTP ──────────────────────────────────────────────────────────


class Qdrant:
    """The few REST calls a bundle needs. Plain HTTP, so tests mock it with respx."""

    def __init__(self, url: str, *, client: httpx.Client | None = None) -> None:
        self._http = client or httpx.Client(base_url=url, timeout=300.0)
        self.url = url

    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = self._http.get(path)
        except httpx.TransportError as exc:
            raise BundleError(
                f"Qdrant is not reachable at {self.url}. Start the stack with `make up`."
            ) from exc
        response.raise_for_status()
        return response.json()

    def version(self) -> str:
        return str(self._get("/")["version"])

    def collection(self, name: str) -> dict[str, Any] | None:
        try:
            return self._get(f"/collections/{name}")["result"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    def vector_size(self, name: str) -> int:
        info = self.collection(name)
        if info is None:
            raise BundleError(f"No Qdrant collection {name!r}.")
        return int(info["config"]["params"]["vectors"]["size"])

    def count(self, name: str) -> int:
        """Exact count. `points_count` in the collection info is approximate."""
        response = self._http.post(f"/collections/{name}/points/count", json={"exact": True})
        response.raise_for_status()
        return int(response.json()["result"]["count"])

    def create_snapshot(self, name: str) -> str:
        response = self._http.post(f"/collections/{name}/snapshots", params={"wait": "true"})
        response.raise_for_status()
        return str(response.json()["result"]["name"])

    def download_snapshot(self, name: str, snapshot: str, dest: IO[bytes]) -> None:
        with self._http.stream("GET", f"/collections/{name}/snapshots/{snapshot}") as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                dest.write(chunk)

    def delete_snapshot(self, name: str, snapshot: str) -> None:
        self._http.delete(f"/collections/{name}/snapshots/{snapshot}").raise_for_status()

    def upload_snapshot(self, name: str, snapshot: IO[bytes]) -> None:
        """Replace the collection with the snapshot's contents."""
        response = self._http.post(
            f"/collections/{name}/snapshots/upload",
            params={"priority": "snapshot", "wait": "true"},
            files={"snapshot": ("collection.snapshot", snapshot)},
        )
        response.raise_for_status()


# ── Export ────────────────────────────────────────────────────────────────────


def _source_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def _check_model_width(model: str, vector_size: int, *, where: str) -> None:
    expected = model_dimensions(model)
    if expected is not None and expected != vector_size:
        raise BundleError(
            f"{where} holds {vector_size}-dimension vectors, but EMBEDDING_MODEL={model} "
            f"produces {expected}. The collection was built with a different model."
        )


def export_bundle(settings: Settings, out_dir: Path, *, qdrant: Qdrant | None = None) -> Path:
    """Package this machine's index. Refuses one that is empty or half-built."""
    qdrant = qdrant or Qdrant(settings.qdrant_url)

    index = JsonCorpusIndex(settings.index_path)
    identity = index.identity()
    if identity.locators == 0:
        raise BundleError(f"The citation index at {settings.index_path} is missing or empty.")

    vector_size = qdrant.vector_size(settings.collection)
    points = qdrant.count(settings.collection)
    if points != identity.locators:
        raise BundleError(
            f"Qdrant holds {points} points but the citation index has {identity.locators} "
            "locators; each locator is one point. Fewer usually means the embedding run "
            "stopped partway; more, that spans were removed since the collection was built. "
            "Re-run the indexer before exporting."
        )
    _check_model_width(settings.embedding_model, vector_size, where="The collection")

    manifest = BundleManifest(
        format_version=FORMAT_VERSION,
        created_at=datetime.now(UTC),
        source_commit=_source_commit(),
        collection=settings.collection,
        embedding_model=settings.embedding_model,
        vector_size=vector_size,
        points=points,
        qdrant_version=qdrant.version(),
        corpus=identity,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"ihl-index-{identity.short_hash}.tar"
    snapshot = qdrant.create_snapshot(settings.collection)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / SNAPSHOT_MEMBER
            with snapshot_path.open("wb") as handle:
                qdrant.download_snapshot(settings.collection, snapshot, handle)
            manifest_path = Path(tmp) / MANIFEST_MEMBER
            manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            partial = target.with_suffix(".tar.partial")
            with tarfile.open(partial, "w") as tar:
                tar.add(manifest_path, arcname=MANIFEST_MEMBER)
                tar.add(settings.index_path, arcname=INDEX_MEMBER)
                tar.add(snapshot_path, arcname=SNAPSHOT_MEMBER)
            partial.replace(target)
    finally:
        # The server keeps every snapshot it makes until told otherwise.
        qdrant.delete_snapshot(settings.collection, snapshot)
    return target


# ── Import ────────────────────────────────────────────────────────────────────


def _member(tar: tarfile.TarFile, name: str) -> IO[bytes]:
    """Read a member by its exact name. Nothing is extracted to disk by path."""
    try:
        info = tar.getmember(name)
    except KeyError as exc:
        raise BundleError(f"Not a bundle: {name} is missing.") from exc
    handle = tar.extractfile(info) if info.isfile() else None
    if handle is None:
        raise BundleError(f"Not a bundle: {name} is not a regular file.")
    return handle


def read_manifest(path: Path) -> BundleManifest:
    with tarfile.open(path, "r") as tar:
        raw = json.loads(_member(tar, MANIFEST_MEMBER).read())
    if raw.get("format_version") != FORMAT_VERSION:
        raise BundleError(
            f"Bundle format {raw.get('format_version')}; this code reads {FORMAT_VERSION}."
        )
    return BundleManifest.model_validate(raw)


def check_compatible(manifest: BundleManifest, settings: Settings, qdrant_version: str) -> None:
    """Every setting that must match before a bundle can be used here."""
    problems = []
    if manifest.embedding_model != settings.embedding_model:
        problems.append(
            f"EMBEDDING_MODEL here is {settings.embedding_model}, but the bundle was "
            f"embedded with {manifest.embedding_model}. Retrieval would compare vectors "
            f"from two models. Set EMBEDDING_MODEL={manifest.embedding_model} in .env "
            "and restart the stack."
        )
    if manifest.collection != settings.collection:
        problems.append(
            f"QDRANT_COLLECTION here is {settings.collection}; the bundle holds "
            f"{manifest.collection}."
        )
    if manifest.qdrant_version != qdrant_version:
        problems.append(
            f"Qdrant here is {qdrant_version}; the bundle came from {manifest.qdrant_version}. "
            "The image is pinned in docker-compose.yml, so one machine is off the pin."
        )
    if problems:
        raise BundleError("The bundle does not match this machine:\n- " + "\n- ".join(problems))


def import_bundle(
    settings: Settings, path: Path, *, qdrant: Qdrant | None = None
) -> BundleManifest:
    """Load a bundle into this machine's Qdrant and citation index, then verify both."""
    qdrant = qdrant or Qdrant(settings.qdrant_url)
    manifest = read_manifest(path)
    check_compatible(manifest, settings, qdrant.version())

    with tarfile.open(path, "r") as tar:
        index_bytes = _member(tar, INDEX_MEMBER).read()
        raw_index = json.loads(index_bytes)
        identity = corpus_identity(raw_index.get("entries", {}), raw_index.get("instruments", []))
        if identity != manifest.corpus:
            raise BundleError(
                "The bundle's citation index does not match its manifest "
                f"({identity.describe()} against {manifest.corpus.describe()}). "
                "The file was altered or truncated in transit."
            )

        # Qdrant first: if it fails, nothing on this machine has changed.
        with tempfile.TemporaryFile() as snapshot:
            shutil.copyfileobj(_member(tar, SNAPSHOT_MEMBER), snapshot)
            snapshot.seek(0)
            qdrant.upload_snapshot(settings.collection, snapshot)

    points = qdrant.count(settings.collection)
    vector_size = qdrant.vector_size(settings.collection)
    if (points, vector_size) != (manifest.points, manifest.vector_size):
        raise BundleError(
            f"After restoring, Qdrant holds {points} points of width {vector_size}; the "
            f"bundle says {manifest.points} of width {manifest.vector_size}. The citation "
            "index was left unchanged."
        )

    index_dir = settings.index_path.parent
    index_dir.mkdir(parents=True, exist_ok=True)
    if settings.index_path.exists():
        shutil.copy2(settings.index_path, settings.index_path.with_suffix(".json.bak"))
    tmp = settings.index_path.with_suffix(".json.tmp")
    tmp.write_bytes(index_bytes)
    tmp.replace(settings.index_path)
    settings.imported_record.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


# ── Status ────────────────────────────────────────────────────────────────────


def status(settings: Settings, *, qdrant: Qdrant | None = None) -> tuple[list[str], list[str]]:
    """What this machine holds, and anything that does not add up.

    Returns (lines to print, problems). Two machines hold the same index when
    their fingerprint lines match.
    """
    qdrant = qdrant or Qdrant(settings.qdrant_url)
    lines: list[str] = []
    problems: list[str] = []

    identity = JsonCorpusIndex(settings.index_path).identity()
    width = model_dimensions(settings.embedding_model)
    lines.append(f"Citation index   {settings.index_path}: {identity.describe()}")
    lines.append(
        f"EMBEDDING_MODEL  {settings.embedding_model}"
        + (f" ({width} dimensions)" if width else " (not in fastembed's catalogue)")
    )
    if identity.locators == 0:
        problems.append("The citation index is missing or empty.")

    points: int | None = None
    try:
        version = qdrant.version()
        info = qdrant.collection(settings.collection)
    except BundleError as exc:
        version, info = "unreachable", None
        problems.append(str(exc))
    else:
        if info is None:
            lines.append(f"Qdrant {version}    no collection {settings.collection!r}")
            problems.append(
                f"No Qdrant collection {settings.collection!r}: retrieval finds nothing."
            )
        else:
            points = qdrant.count(settings.collection)
            size = int(info["config"]["params"]["vectors"]["size"])
            lines.append(
                f"Qdrant {version}    {settings.collection}: {points} points, {size} dimensions"
            )
            if points != identity.locators:
                problems.append(
                    f"Qdrant holds {points} points but the citation index has "
                    f"{identity.locators} locators. They come from different builds, or "
                    "the embedding run stopped partway."
                )
            if width is not None and size != width:
                problems.append(
                    f"The collection's vectors are {size}-dimensional but {settings.embedding_model} "
                    f"produces {width}: it was built with another model."
                )

    if settings.imported_record.exists():
        imported = BundleManifest.model_validate_json(
            settings.imported_record.read_text(encoding="utf-8")
        )
        lines.append(f"Imported bundle  built {imported.created_at:%Y-%m-%d %H:%M} UTC")
        if imported.corpus != identity:
            problems.append(
                "The citation index has changed since the bundle was imported "
                "(re-fetched or re-indexed here?)."
            )
        if imported.embedding_model != settings.embedding_model:
            problems.append(
                f"The imported bundle was embedded with {imported.embedding_model}, but "
                f"EMBEDDING_MODEL is now {settings.embedding_model}."
            )

    lines.append("")
    lines.append("Fingerprint: " + fingerprint(identity, settings.embedding_model, points, version))
    return lines, problems


# ── CLI ───────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Package this machine's index.")
    export.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "bundles")
    imp = commands.add_parser("import", help="Load a bundle into this machine.")
    imp.add_argument("bundle", type=Path)
    commands.add_parser("status", help="Show this machine's index and check it adds up.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # The resolver logs every index load; in a report meant to be read, that is noise.
    configure_logging(level=os.getenv("LOG_LEVEL", "WARNING"))
    settings = Settings.from_environment()
    try:
        if args.command == "export":
            path = export_bundle(settings, args.out)
            manifest = read_manifest(path)
            print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
            print(f"Fingerprint: {manifest.describe()}")
            print("Send it privately; it holds the corpus text, and the repo is public.")
        elif args.command == "import":
            manifest = import_bundle(settings, args.bundle)
            print(f"Imported. Fingerprint: {manifest.describe()}")
            print("Restart the API so it reloads the citation index: docker compose restart api")
        else:
            lines, problems = status(settings)
            print("\n".join(lines))
            if problems:
                print("\nProblems:\n- " + "\n- ".join(problems), file=sys.stderr)
                return 1
    except BundleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
