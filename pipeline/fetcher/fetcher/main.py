"""Corpus fetcher entrypoint.

Reads the manifests under `corpus/manifests/` and downloads exactly what they
list. It never crawls: the manifest is the scope, so every change to the corpus
is a reviewable diff.

    make fetch

Each instrument is written to `data/cache/<id>.json` as a `CorpusDocument` --
the shape every source normalises to. Raw API responses are kept alongside, so
a change in an undocumented upstream shows up as a diff rather than as a corpus
that quietly lost articles.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import structlog

from council_core.telemetry import configure_logging
from fetcher.parsers.treaty import parse_treaty
from fetcher.sources.icrc import IcrcClient, IcrcFetchError

log = structlog.get_logger(__name__)

CORPUS_DIR = Path(os.getenv("CORPUS_DIR", "/corpus"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = DATA_DIR / "cache"
RAW_DIR = CACHE_DIR / "raw"


def load_manifest(name: str) -> dict:
    """Read one manifest from `corpus/manifests/`."""
    path = CORPUS_DIR / "manifests" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_treaties(manifest: dict, client: IcrcClient) -> tuple[int, int]:
    """Fetch every instrument the treaty manifest lists.

    One instrument failing does not stop the others: a partial corpus that
    says what is missing is more useful than no corpus at all.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched = failed = 0

    # Hague IV and its annexed Regulations are two corpus ids served by one
    # node (ADR 0010), so the same response is parsed twice with a different
    # section filter rather than requested twice.
    entries_by_node: dict[str, list[dict]] = {}

    for instrument in manifest["instruments"]:
        corpus_id = instrument["id"]
        node = instrument["icrc_node"]
        try:
            if node not in entries_by_node:
                entries_by_node[node] = client.fetch_treaty_content(node)

            document = parse_treaty(
                corpus_id=corpus_id,
                title=instrument["title"],
                source_url=instrument["source_url"],
                entries=entries_by_node[node],
                section=instrument.get("icrc_section", "Article"),
                year=instrument.get("year"),
            )
            if not document.spans:
                raise IcrcFetchError(
                    f"{corpus_id} parsed to zero spans. The section filter "
                    f"{instrument.get('icrc_section', 'Article')!r} probably no longer matches."
                )

            out = CACHE_DIR / f"{corpus_id}.json"
            out.write_text(
                document.model_dump_json(indent=2, exclude_none=True) + "\n",
                encoding="utf-8",
            )
            fetched += 1
            log.info("instrument_fetched", id=corpus_id, spans=len(document.spans), path=str(out))

        except Exception as exc:
            failed += 1
            log.error("instrument_failed", id=corpus_id, error=str(exc))

    return fetched, failed


def main() -> None:
    """Fetch everything the manifests list."""
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    treaties = load_manifest("treaties")
    cases = load_manifest("cases")
    resolutions = load_manifest("resolutions")

    log.info(
        "fetch_scope",
        treaties=len(treaties["instruments"]),
        cases=len(cases["cases"]),
        resolutions=len(resolutions["resolutions"]),
    )

    with IcrcClient(cache_dir=RAW_DIR) as client:
        fetched, failed = fetch_treaties(treaties, client)

    log.info("fetch_complete", fetched=fetched, failed=failed)

    # Tier 2 and 3. Judgments are PDFs from four tribunals with different
    # layouts, and are a stretch goal for v1 -- see docs/corpus.md.
    if cases["cases"] or resolutions["resolutions"]:
        log.warning(
            "sources_not_implemented",
            cases=len(cases["cases"]),
            resolutions=len(resolutions["resolutions"]),
            next_step="treaties only in v1; see docs/corpus.md",
        )

    if failed:
        raise SystemExit(f"{failed} instrument(s) failed. See the errors above.")


if __name__ == "__main__":
    main()
