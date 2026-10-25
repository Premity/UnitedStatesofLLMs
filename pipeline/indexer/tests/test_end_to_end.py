"""fetch -> parse -> index -> resolve, over two instruments (T1-7).

Each stage has its own tests. This one exists because the stages can each be
correct and still not compose: the fetcher's output shape, the parser's
locator spelling and the resolver's lookup key all have to agree exactly, and
nothing raises when they do not. A citation simply fails to resolve, and the
metrics read that as the model inventing law.

Runs against saved API responses, so `make test` still touches no network
(non-negotiable #8). Qdrant is not involved: embedding is slow and needs a
running service, while the citation index -- which is what citation validation
actually reads -- needs neither.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fetcher.parsers.treaty import parse_treaty
from fetcher.sources.icrc import IcrcClient
from indexer.index.citation_index import write_index

from council_core.citations.resolver import CitationResolver, JsonCorpusIndex
from council_core.models.citation import Citation, CitationStatus, CitationType

FIXTURES = Path(__file__).resolve().parents[2] / "fetcher" / "tests" / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def client_serving(payload: dict) -> IcrcClient:
    """A client wired to a saved response instead of the network."""
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, json=payload, headers={"content-type": "application/vnd.api+json"}
        )
    )
    return IcrcClient(client=httpx.Client(transport=transport, base_url="https://icrc.test"))


@pytest.fixture(scope="module")
def index_path(tmp_path_factory) -> Path:
    """Drive the real pipeline over two instruments and write the index."""
    with client_serving(load("icrc_ap_i_slice.json")) as client:
        ap_i_entries = client.fetch_treaty_content("ap-i-uuid")
    with client_serving(load("icrc_hague_slice.json")) as client:
        hague_entries = client.fetch_treaty_content("hague-uuid")

    documents = [
        parse_treaty(
            corpus_id="ap_i",
            title="Protocol Additional I",
            source_url="https://example.org/ap_i",
            entries=ap_i_entries,
            year=1977,
        ),
        # One node, two corpus ids, split by section -- ADR 0010.
        parse_treaty(
            corpus_id="hague_iv",
            title="Hague Convention IV",
            source_url="https://example.org/hague",
            entries=hague_entries,
            section="Article",
            year=1907,
        ),
        parse_treaty(
            corpus_id="hague_iv_regs",
            title="Hague Regulations",
            source_url="https://example.org/hague",
            entries=hague_entries,
            section="Annex",
            year=1907,
        ),
    ]

    path = tmp_path_factory.mktemp("corpus") / "citation_index.json"
    write_index(documents, path)
    return path


@pytest.fixture(scope="module")
def resolver(index_path: Path) -> CitationResolver:
    return CitationResolver(JsonCorpusIndex(index_path))


def treaty(instrument: str, article: str, quote: str | None = None) -> Citation:
    return Citation(
        type=CitationType.TREATY, instrument=instrument, article=article, quoted_text=quote
    )


@pytest.mark.parametrize(
    ("expected", "citation", "why"),
    [
        (
            CitationStatus.RESOLVED,
            treaty("ap_i", "51(2)"),
            "a sub-paragraph the parser had to recover from the article body",
        ),
        (
            CitationStatus.UNRESOLVED,
            treaty("ap_i", "999"),
            "an indexed instrument with no such article -- the fabrication signal",
        ),
        (
            CitationStatus.OUT_OF_CORPUS,
            treaty("gc_iii", "13"),
            "a real instrument we did not index -- a coverage limit, not a fabrication",
        ),
        (
            CitationStatus.MISQUOTED,
            treaty("ap_i", "51(2)", "Cats are prohibited from wearing hats."),
            "the locator resolves but the quotation is not in the text",
        ),
    ],
)
def test_all_four_citation_statuses_come_out_of_a_real_pipeline_run(
    resolver: CitationResolver, expected: CitationStatus, citation: Citation, why: str
) -> None:
    assert resolver.resolve(citation).status is expected, why


def test_a_whole_article_and_a_subparagraph_are_separate_locators(
    resolver: CitationResolver,
) -> None:
    """ADR 0008. They carry different text, and a quotation is checked against
    whichever one was cited."""
    article = resolver.resolve(treaty("ap_i", "51"))
    paragraph = resolver.resolve(treaty("ap_i", "51(2)"))

    assert article.status is CitationStatus.RESOLVED
    assert paragraph.status is CitationStatus.RESOLVED
    assert article.corpus_text != paragraph.corpus_text


def test_the_hague_regulations_do_not_answer_for_the_convention(
    resolver: CitationResolver,
) -> None:
    """Both documents have an article 3 saying different things, and only the
    Regulations have an article 23. Under one corpus id a citation would
    resolve against whichever text the index happened to hold, and the judge
    would check the quotation against the wrong provision. ADR 0010.
    """
    convention = resolver.resolve(treaty("hague_iv", "3"))
    regulations = resolver.resolve(treaty("hague_iv_regs", "3"))

    assert convention.status is CitationStatus.RESOLVED
    assert regulations.status is CitationStatus.RESOLVED
    assert convention.corpus_text != regulations.corpus_text

    # The Convention stops at article 9, so this is a real error and is
    # reported as one rather than silently returning Regulations text.
    assert resolver.resolve(treaty("hague_iv", "23")).status is CitationStatus.UNRESOLVED
    assert resolver.resolve(treaty("hague_iv_regs", "23")).status is CitationStatus.RESOLVED


def test_a_genuine_quotation_resolves(resolver: CitationResolver) -> None:
    """The text stored must be verbatim enough that a real quotation matches.
    A paraphrase anywhere in the pipeline would surface here as `misquoted`,
    which reads downstream as the model misquoting the law."""
    citation = treaty("ap_i", "51(2)", "shall not be the object of attack")
    assert resolver.resolve(citation).status is CitationStatus.RESOLVED


def test_the_index_distinguishes_indexed_instruments_from_everything_else(
    index_path: Path,
) -> None:
    """`instruments` is what separates `unresolved` from `out_of_corpus`.
    Without it every miss looks like fabrication. Non-negotiable #2."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert set(index["instruments"]) == {"ap_i", "hague_iv", "hague_iv_regs"}
    assert index["entries"]
