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
from fetcher.parsers.customary import parse_customary_rules
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


def mark_fetched(manifest_name: str, fetched_ids: set[str]) -> None:
    """Flip `status` to "fetched" for what actually landed.

    The manifest is the corpus scope and the record of what is in it, so a
    status left at "pending" after a successful fetch makes the manifest lie
    about the corpus. Written back in place: this is a committed file, so the
    change is a reviewable diff.
    """
    path = CORPUS_DIR / "manifests" / f"{manifest_name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for entry in data.get("instruments", []):
        want = "fetched" if entry["id"] in fetched_ids else "pending"
        if entry.get("status") != want:
            entry["status"] = want
            changed += 1
    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log.info("manifest_updated", manifest=manifest_name, changed=changed)


def fetch_treaties(manifest: dict, client: IcrcClient) -> tuple[int, int]:
    """Fetch every instrument the treaty manifest lists.

    One instrument failing does not stop the others: a partial corpus that
    says what is missing is more useful than no corpus at all.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched_ids: set[str] = set()
    failed = 0

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
            fetched_ids.add(corpus_id)
            log.info("instrument_fetched", id=corpus_id, spans=len(document.spans), path=str(out))

        except Exception as exc:
            failed += 1
            log.error("instrument_failed", id=corpus_id, error=str(exc))

    mark_fetched("treaties", fetched_ids)
    return len(fetched_ids), failed


def fetch_customary(client: IcrcClient) -> bool:
    """Fetch the 161 customary IHL rules.

    `CitationType.CUSTOMARY` has always rendered `customary_ihl/rule.14`, and
    until this lands nothing resolves it -- every correct citation to a
    customary rule reads as a model inventing authority.
    """
    try:
        document = parse_customary_rules(entries=client.fetch_customary_rules())
        if len(document.spans) < 150:
            raise IcrcFetchError(
                f"Only {len(document.spans)} customary rules parsed; the study has 161. "
                "The rule body markup has probably changed."
            )
        out = CACHE_DIR / f"{document.id}.json"
        out.write_text(
            document.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8"
        )
        log.info("customary_fetched", rules=len(document.spans), path=str(out))
        return True
    except Exception as exc:
        log.error("customary_failed", error=str(exc))
        return False


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
        if fetch_customary(client):
            fetched += 1
        else:
            failed += 1

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
