"""Build the citation index the runtime resolver reads.

The index is two things, and both matter:

- `entries` maps a locator to its text, which is what resolves a citation and
  what a quotation is checked against.
- `instruments` lists what we indexed at all. It is the only thing separating
  `unresolved` -- a locator missing from an instrument we *do* hold, which is
  the fabrication signal -- from `out_of_corpus`, a real authority we chose not
  to index. Without it every miss looks like fabrication and the metric is
  worthless. Non-negotiable #2, ADR 0004.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from council_core.models.corpus import CorpusDocument

log = structlog.get_logger(__name__)

INDEX_VERSION = "0.1.0"


def build_index(documents: list[CorpusDocument]) -> dict[str, Any]:
    """Collapse documents into the flat structure `JsonCorpusIndex` reads."""
    entries: dict[str, dict[str, str]] = {}
    instruments: list[str] = []

    for doc in documents:
        if doc.id not in instruments:
            instruments.append(doc.id)
        for span in doc.spans:
            if span.locator in entries:
                # Two documents claiming one locator means one silently wins,
                # and which one depends on iteration order.
                raise ValueError(
                    f"Locator {span.locator!r} is produced by more than one document. "
                    "A locator addresses exactly one provision."
                )
            entries[span.locator] = {
                "text": span.text,
                "source_url": doc.source_url,
            }

    return {
        "version": INDEX_VERSION,
        "instruments": sorted(instruments),
        "entries": entries,
    }


def write_index(documents: list[CorpusDocument], path: Path) -> dict[str, Any]:
    """Build the index and write it atomically.

    Written to a temporary file and moved into place, because the runtime reads
    this path: a half-written index would be read as a corpus that has lost
    most of its articles.
    """
    index = build_index(documents)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)

    log.info(
        "citation_index_written",
        path=str(path),
        entries=len(index["entries"]),
        instruments=len(index["instruments"]),
    )
    return index
