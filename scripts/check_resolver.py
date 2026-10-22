"""Check that all four citation statuses come out against the stub index. Development aid."""

import inspect
import os
from pathlib import Path

from council_core.citations.resolver import CitationResolver, JsonCorpusIndex
from council_core.models.citation import Citation, CitationStatus, CitationType

INDEX_PATH = Path(os.environ.get("DATA_DIR", "data")) / "index" / "citation_index.json"


def build_index() -> JsonCorpusIndex:
    params = inspect.signature(JsonCorpusIndex).parameters
    if params:
        print(f"CorpusIndex({INDEX_PATH})  params={list(params)}")
        return JsonCorpusIndex(INDEX_PATH)
    print("CorpusIndex()  (reads its path from settings)")
    return JsonCorpusIndex()


def treaty(instrument: str, article: str, quote: str | None = None) -> Citation:
    return Citation(
        type=CitationType.TREATY, instrument=instrument, article=article, quoted_text=quote
    )


CASES = [
    (
        "resolved",
        treaty("ap_i", "51(2)", "shall not be the object of attack"),
        CitationStatus.RESOLVED,
    ),
    ("unresolved", treaty("ap_i", "999"), CitationStatus.UNRESOLVED),
    ("out_of_corpus", treaty("gc_i", "3"), CitationStatus.OUT_OF_CORPUS),
    (
        "misquoted",
        treaty(
            "ap_i", "51(2)", "Belligerents may freely bombard towns at night without restriction."
        ),
        CitationStatus.MISQUOTED,
    ),
]


def main() -> None:
    if not INDEX_PATH.exists():
        raise SystemExit(
            f"Index not found at {INDEX_PATH}. Did you run: source scripts/dev-env.sh ?"
        )
    resolver = CitationResolver(build_index())
    for label, citation, expected in CASES:
        result = resolver.resolve(citation)
        ok = "OK  " if result.status == expected else "FAIL"
        print(
            f"{ok} {label:14} {citation.locator():22} -> {result.status.value}  ({result.note or ''})"
        )


if __name__ == "__main__":
    main()
