"""The rebuttal trims whole long articles to the provisions the debate cited.

On Groq's free tier the presenter's model refuses a request over 8,000 tokens a
minute, and the full council's round 2 on Galić was refused at 8,278. About
2,000 of those tokens were one span: the whole of Rome Statute art. 8.
"""

from __future__ import annotations

from app.roles.presenter import REBUTTAL_SPAN_CHAR_LIMIT, rebuttal_context
from council_core.models.citation import Citation, CitationStatus, ResolvedCitation
from council_core.models.debate import Argument, Objection, Role

LONG = "x" * (REBUTTAL_SPAN_CHAR_LIMIT + 1)


def _span(article: str, text: str, instrument: str = "rome_statute") -> ResolvedCitation:
    citation = Citation(type="treaty", instrument=instrument, article=article)
    return ResolvedCitation(citation=citation, status=CitationStatus.RESOLVED, corpus_text=text)


def _argument(*cited: ResolvedCitation) -> Argument:
    return Argument(
        claim="c",
        reasoning="r",
        citations=[rc.citation for rc in cited],
        resolved_citations=list(cited),
    )


def _objection(*cited: ResolvedCitation) -> Objection:
    return Objection(
        raised_by=Role.ATTACKER_EVIDENTIARY,
        target_argument_id="arg_1",
        ground="g",
        reasoning="r",
        citations=[rc.citation for rc in cited],
        resolved_citations=list(cited),
    )


def _locators(spans: list[ResolvedCitation]) -> list[str]:
    return [s.citation.locator() for s in spans]


def test_a_long_article_is_replaced_by_the_provisions_cited_inside_it() -> None:
    art8 = _span("8", LONG)
    b_iv = _span("8(2)(b)(iv)", "Intentionally launching an attack ...")
    a_iv = _span("8(2)(a)(iv)", "Extensive destruction ...")
    ap_i = _span("51(2)", "The civilian population ...", instrument="ap_i")

    got = rebuttal_context([ap_i, art8], [_argument(b_iv, ap_i)], [_objection(a_iv)])

    assert _locators(got) == [
        "ap_i/art.51(2)",
        "rome_statute/art.8(2)(b)(iv)",
        "rome_statute/art.8(2)(a)(iv)",
    ]
    assert got[1].corpus_text == "Intentionally launching an attack ..."


def test_a_cited_provision_already_retrieved_is_not_shown_twice() -> None:
    b_i = _span("8(2)(b)(i)", "Intentionally directing attacks ...")
    got = rebuttal_context([_span("8", LONG), b_i], [_argument(b_i)], [])
    assert _locators(got) == ["rome_statute/art.8(2)(b)(i)"]


def test_a_long_article_cited_as_a_whole_is_kept_whole() -> None:
    art8 = _span("8", LONG)
    assert rebuttal_context([art8], [_argument(art8)], []) == [art8]


def test_an_uncited_long_article_is_dropped_and_short_spans_are_untouched() -> None:
    short = [_span("51(2)", "a", instrument="ap_i"), _span("57", "b" * 2600, instrument="ap_i")]
    got = rebuttal_context([short[0], _span("8", LONG), short[1]], [], [])
    assert got == short


def test_only_provisions_inside_the_article_replace_it() -> None:
    # art.80 and art.8bis begin with "8" but are not inside art. 8.
    eighty = _span("80(1)", "other")
    bis = _span("8bis(2)(a)", "aggression")
    got = rebuttal_context([_span("8", LONG)], [_argument(eighty, bis)], [])
    assert got == []


def test_a_citation_that_did_not_resolve_brings_no_text() -> None:
    invented = ResolvedCitation(
        citation=Citation(type="treaty", instrument="rome_statute", article="8(2)(b)(xcix)"),
        status=CitationStatus.UNRESOLVED,
    )
    assert rebuttal_context([_span("8", LONG)], [_argument(invented)], []) == []
