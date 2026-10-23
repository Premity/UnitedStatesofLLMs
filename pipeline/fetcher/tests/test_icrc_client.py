"""The ICRC client, against saved responses rather than the network.

`make test` never touches the network (non-negotiable #8), so these drive the
client through a mock transport. The fixture is a real slice of the AP I
response, so the shape under test is the shape the API actually returns.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fetcher.sources.icrc import USER_AGENT, IcrcClient, IcrcFetchError

FIXTURES = Path(__file__).parent / "fixtures"
AP_I_SLICE = json.loads((FIXTURES / "icrc_ap_i_slice.json").read_text(encoding="utf-8"))

# What the site serves for any path it does not recognise -- with status 200.
SPA_SHELL = "<!doctype html><html><head><title>IHL Databases</title></head><body></body></html>"


def client_for(handler) -> IcrcClient:
    transport = httpx.MockTransport(handler)
    return IcrcClient(client=httpx.Client(transport=transport, base_url="https://icrc.test"))


def json_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload, headers={"content-type": "application/vnd.api+json"})


def test_fetches_the_entries_of_a_treaty() -> None:
    with client_for(lambda _: json_response(AP_I_SLICE)) as client:
        entries = client.fetch_treaty_content("some-uuid")

    assert len(entries) == 2
    assert {e["field_treaty_content_unid"] for e in entries} == {"article-48", "article-51"}


def test_the_spa_shell_is_rejected_even_though_it_is_a_200() -> None:
    """The site answers 200 with its HTML shell for unknown paths.

    Checking only the status would accept a page with no treaty text in it,
    and the corpus would come out empty with no error anywhere.
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=SPA_SHELL, headers={"content-type": "text/html"})

    with client_for(handler) as client, pytest.raises(IcrcFetchError, match="not JSON"):
        client.fetch_treaty_content("some-uuid")


def test_an_empty_node_is_an_error_not_an_empty_corpus() -> None:
    """A wrong uuid or a renamed field would otherwise index zero articles
    and report success."""
    with (
        client_for(lambda _: json_response({"data": []})) as client,
        pytest.raises(IcrcFetchError, match="no entries"),
    ):
        client.fetch_treaty_content("some-uuid")


def test_http_errors_are_raised() -> None:
    with (
        client_for(lambda _: httpx.Response(404)) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.fetch_treaty_content("missing")


def test_raw_responses_are_snapshotted(tmp_path: Path) -> None:
    """The API is undocumented, so a shape change has to surface as a diff
    rather than as a corpus that quietly lost articles."""
    transport = httpx.MockTransport(lambda _: json_response(AP_I_SLICE))
    with IcrcClient(
        client=httpx.Client(transport=transport, base_url="https://icrc.test"),
        cache_dir=tmp_path,
    ) as client:
        client.fetch_treaty_content("abc-123")

    snapshot = tmp_path / "icrc_abc-123.json"
    assert snapshot.exists()
    assert json.loads(snapshot.read_text(encoding="utf-8"))["data"]


def test_listing_follows_pagination() -> None:
    """The API caps a page at 50, and there are over a hundred treaties."""
    pages = [
        {"data": [{"id": f"n{i}"} for i in range(50)]},
        {"data": [{"id": f"m{i}"} for i in range(11)]},
    ]
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("page[offset]", 0))
        calls.append(offset)
        return json_response(pages[0] if offset == 0 else pages[1])

    with client_for(handler) as client:
        rows = client.list_treaties(page_size=50)

    assert len(rows) == 61
    assert calls == [0, 50]


def test_the_client_identifies_itself() -> None:
    """These are public institutional archives; say who is calling."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return json_response(AP_I_SLICE)

    transport = httpx.MockTransport(handler)
    with IcrcClient(
        client=httpx.Client(
            transport=transport,
            base_url="https://icrc.test",
            headers={"User-Agent": USER_AGENT},
        )
    ) as client:
        client.fetch_treaty_content("x")

    assert "UnitedStatesofLLMs" in seen["user-agent"]


def test_parsing_the_fixture_yields_resolvable_locators() -> None:
    """The client and parser agree on the shape, end to end."""
    from fetcher.parsers.treaty import parse_treaty

    with client_for(lambda _: json_response(AP_I_SLICE)) as client:
        entries = client.fetch_treaty_content("uuid")

    doc = parse_treaty(
        corpus_id="ap_i", title="AP I", source_url="https://example.org", entries=entries
    )
    locators = {s.locator for s in doc.spans}
    assert "ap_i/art.48" in locators
    assert "ap_i/art.51(2)" in locators
