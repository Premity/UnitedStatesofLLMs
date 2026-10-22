"""Corpus fetcher entrypoint.

Reads the manifests under `corpus/manifests/` and downloads exactly what they
list. It never crawls: the manifest is the scope, so every change to the corpus
is a reviewable diff.

    make fetch

STATUS: scaffold. The manifest loading, CLI, and output layout are settled; the
per-source parsers are not yet implemented. See `docs/corpus.md` for the target
document shape and `ISSUES.md` for what remains.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import structlog

from council_core.telemetry import configure_logging

log = structlog.get_logger(__name__)

CORPUS_DIR = Path(os.getenv("CORPUS_DIR", "/corpus"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = DATA_DIR / "cache"


def load_manifest(name: str) -> dict:
    """Read one manifest from `corpus/manifests/`."""
    path = CORPUS_DIR / "manifests" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    """Fetch everything the manifests list."""
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    treaties = load_manifest("treaties")
    cases = load_manifest("cases")
    resolutions = load_manifest("resolutions")

    log.info(
        "fetch_scope",
        treaties=len(treaties["instruments"]),
        cases=len(cases["cases"]),
        resolutions=len(resolutions["resolutions"]),
    )

    # TODO(#2): implement the source fetchers.
    #   - ICRC IHL database (treaties)   -> app/sources/icrc.py
    #   - ICC court records (judgments)  -> app/sources/icc.py
    #   - ICTY/ICTR archives             -> app/sources/icty.py
    #   - ICJ case documents             -> app/sources/icj.py
    #   - UN Digital Library             -> app/sources/un.py
    #
    # Each source normalises to the paragraph-addressable document shape in
    # docs/corpus.md, writes to data/cache/<id>.json, and flips the manifest
    # entry's status to "fetched".
    log.warning("fetcher_not_implemented", next_step="see docs/corpus.md and ISSUES.md")


if __name__ == "__main__":
    main()
