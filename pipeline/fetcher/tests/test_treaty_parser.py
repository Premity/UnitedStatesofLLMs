"""Turning an ICRC treaty node into spans the resolver can find."""

from __future__ import annotations

from fetcher.parsers.treaty import article_number, html_to_chunks, parse_treaty


def entry(unid: str, content: str, section: str = "Article", title: str | None = None) -> dict:
    return {
        "field_treaty_content_unid": unid,
        "field_treaty_content_content": content,
        "field_treaty_content_section": section,
        "field_treaty_content_title": title,
    }


def locators(doc) -> list[str]:
    return [s.locator for s in doc.spans]


def build(entries: list[dict], **kw):
    return parse_treaty(
        corpus_id=kw.pop("corpus_id", "ap_i"),
        title="A treaty",
        source_url="https://example.org/t",
        entries=entries,
        **kw,
    )


def test_subparagraphs_split_into_their_own_spans() -> None:
    """A model cites `51(2)`, so the index must hold `51(2)` and not only `51`."""
    doc = build([entry("article-51", "<p>1. First para.</p><p>2. Second para.</p>")])
    assert locators(doc) == ["ap_i/art.51", "ap_i/art.51(1)", "ap_i/art.51(2)"]


def test_the_whole_article_is_indexed_too() -> None:
    """ADR 0008: `art.51` and `art.51(2)` are distinct locators, and a
    quotation is checked against whichever was cited."""
    doc = build([entry("article-51", "<p>1. First.</p><p>2. Second.</p>")])
    whole = doc.spans[0]
    assert whole.locator == "ap_i/art.51"
    assert "First." in whole.text and "Second." in whole.text


def test_unnumbered_prose_is_kept_whole() -> None:
    """Most Geneva Convention articles have no paragraph numbers. Inventing
    `(1)` would create a locator nobody cites."""
    doc = build(
        [entry("article-13", "<p>Prisoners of war must at all times be humanely treated.</p>")],
        corpus_id="gc_iii",
    )
    assert locators(doc) == ["gc_iii/art.13"]


def test_subparagraphs_point_at_their_article() -> None:
    """The parent link gives the embedder context for a one-line provision
    without merging two citable units into one chunk."""
    doc = build([entry("article-51", "<p>1. First.</p>")])
    assert doc.spans[1].parent == "ap_i/art.51"


def test_deep_nesting_survives() -> None:
    """The Rome Statute's article 8 is the deepest in the corpus."""
    doc = build(
        [
            entry(
                "article-8",
                "<p>2. means:</p><p>(b) Other serious violations:</p>"
                "<p>(i) Attacks against civilians;</p><p>(ii) Attacks on civilian objects;</p>"
                "<p>(iii) Attacks on humanitarian personnel;</p><p>(iv) Launching an attack;</p>",
            )
        ],
        corpus_id="rome_statute",
    )
    assert "rome_statute/art.8(2)(b)(iv)" in locators(doc)
    assert "rome_statute/art.8(2)(b)(i)" in locators(doc)


def test_section_selects_which_document_an_entry_belongs_to() -> None:
    """Hague IV is two corpus ids served by one node: the Convention takes
    `Article`, the annexed Regulations take `Annex`. ADR 0010."""
    entries = [
        entry("article-3", "<p>Convention article three.</p>", section="Article"),
        entry("regulations-art-3", "<p>Regulations article three.</p>", section="Annex"),
    ]
    convention = build(entries, corpus_id="hague_iv", section="Article")
    regulations = build(entries, corpus_id="hague_iv_regs", section="Annex")

    assert locators(convention) == ["hague_iv/art.3"]
    assert locators(regulations) == ["hague_iv_regs/art.3"]
    assert convention.spans[0].text != regulations.spans[0].text


def test_non_article_entries_are_skipped() -> None:
    """Tables of contents and chapter headings are not citable provisions."""
    doc = build(
        [
            entry("toc", "<p>Table of contents</p>"),
            entry("chapter-1", "<p>Chapter I</p>"),
            entry("article-1", "<p>Real text.</p>"),
        ]
    )
    assert locators(doc) == ["ap_i/art.1"]


def test_empty_articles_produce_no_span() -> None:
    """A blank span makes every quotation against it resolve `misquoted`."""
    assert build([entry("article-1", "")]).spans == []


def test_bis_articles_keep_their_suffix() -> None:
    """The 2010 aggression amendment adds `8bis`, `15bis`, `15ter`."""
    doc = build(
        [entry("article-8bis", "<p>1. For the purpose of this Statute:</p>")],
        corpus_id="rome_statute",
    )
    assert locators(doc)[0] == "rome_statute/art.8bis"


class TestHtmlToChunks:
    def test_paragraphs_become_separate_chunks(self) -> None:
        assert html_to_chunks("<p>One.</p><p>Two.</p>") == ["One.", "Two."]

    def test_items_sharing_one_paragraph_are_split(self) -> None:
        """AP I packs `(a)`, `(b)` and `(c)` into a single `<p>` separated by
        line breaks, while the Rome Statute gives each its own."""
        markup = "<p>(a) first;<br/>(b) second;<br/>(c) third;</p>"
        assert html_to_chunks(markup) == ["(a) first;", "(b) second;", "(c) third;"]

    def test_entities_are_decoded(self) -> None:
        assert html_to_chunks("<p>attacks &amp; reprisals</p>") == ["attacks & reprisals"]

    def test_markup_inside_a_paragraph_is_dropped(self) -> None:
        assert html_to_chunks("<p>a <em>word</em> here</p>") == ["a word here"]

    def test_empty_markup_is_empty(self) -> None:
        assert html_to_chunks("") == []


class TestArticleNumber:
    def test_plain_article(self) -> None:
        assert article_number("article-51") == "51"

    def test_regulations_article(self) -> None:
        assert article_number("regulations-art-23") == "23"

    def test_bis(self) -> None:
        assert article_number("article-8bis") == "8bis"

    def test_non_article(self) -> None:
        assert article_number("preamble") is None
        assert article_number("") is None
