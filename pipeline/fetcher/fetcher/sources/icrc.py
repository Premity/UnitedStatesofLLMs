"""Fetch treaty text from the ICRC IHL Databases.

The ICRC website is a single-page app -- every URL returns the same HTML shell
with no treaty text in it. The text comes from the Drupal JSON:API behind it,
which is public and unauthenticated:

    /jsonapi/node/treaty                              every treaty, 50 per page
    /jsonapi/node/treaty/{uuid}/field_treaty_content  one treaty, by article

That API is **undocumented**. There is no published contract, no versioning and
no deprecation notice, so every raw response is written to the cache before
anything parses it. When the shape changes -- and it will -- the failure shows
up as a diff against a snapshot rather than as a corpus that quietly lost half
its articles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)

BASE_URL = "https://ihl-databases.icrc.org"
NODE_PATH = "/jsonapi/node/treaty"

# These are public institutional archives. Identify the client, and keep the
# request count to roughly one per document.
USER_AGENT = (
    "UnitedStatesofLLMs/0.1 (academic research; https://github.com/Premity/UnitedStatesofLLMs)"
)

RETRYABLE = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)


class IcrcFetchError(RuntimeError):
    """The API answered with something we cannot use."""


class IcrcClient:
    """Reads treaty documents from the ICRC JSON:API."""

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        cache_dir: Path | None = None,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._cache = cache_dir
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.api+json"},
        )

    def __enter__(self) -> IcrcClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(RETRYABLE),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """One request, with the SPA-shell trap checked.

        The site answers 200 with its HTML shell for any path it does not
        recognise, so a status check alone would accept a page with no treaty
        text in it as success.
        """
        url = f"{self._base}{path}"
        response = self._client.get(url, params=params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            raise IcrcFetchError(
                f"{url} returned {content_type!r}, not JSON. The JSON:API path has probably "
                "moved: the site serves its HTML shell with status 200 for unknown paths."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise IcrcFetchError(f"{url} returned a body that is not JSON.") from exc

    def list_treaties(self, *, page_size: int = 50) -> list[dict]:
        """Every treaty node, following the API's pagination."""
        rows: list[dict] = []
        offset = 0
        while True:
            payload = self._get(
                NODE_PATH,
                params={"page[offset]": offset, "page[limit]": page_size},
            )
            batch = payload.get("data", [])
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        log.info("icrc_treaties_listed", count=len(rows))
        return rows

    def fetch_treaty_content(self, node_uuid: str) -> list[dict]:
        """The article entries of one treaty, newest snapshot written to cache.

        Returns the `attributes` of each entry -- the unid, section, title and
        the HTML body -- which is what the parser reads.
        """
        payload = self._get(f"{NODE_PATH}/{node_uuid}/field_treaty_content")
        self._snapshot(node_uuid, payload)

        entries = [row.get("attributes", {}) for row in payload.get("data", [])]
        if not entries:
            raise IcrcFetchError(
                f"Node {node_uuid} returned no entries. Either the uuid is wrong or the "
                "field name has changed."
            )
        log.info("icrc_treaty_fetched", node=node_uuid, entries=len(entries))
        return entries

    def _snapshot(self, node_uuid: str, payload: dict) -> None:
        """Keep the raw response, so a shape change is a diff and not a mystery."""
        if self._cache is None:
            return
        self._cache.mkdir(parents=True, exist_ok=True)
        path = self._cache / f"icrc_{node_uuid}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
