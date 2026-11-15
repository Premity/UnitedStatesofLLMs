"""Where the harness finds Qdrant when it runs on the host rather than in Docker.

`.env` gives Qdrant's address inside the compose network (http://qdrant:6333),
and so does the app's own default. The host cannot resolve `qdrant`: retrieval
then fails in arms B-E while arm A, which retrieves nothing, succeeds, so the
run looks partial rather than broken (found in the #25 rehearsal). The dev
stack publishes Qdrant on localhost.

Decided by the hostname, not by whether QDRANT_URL is set: `.env` is in
os.environ before the harness can look (LiteLLM loads it on import), so "set"
proves nothing, while `qdrant` never resolves outside the compose network.
"""

from __future__ import annotations

from urllib.parse import urlparse

HOST_QDRANT_URL = "http://localhost:6333"


def host_qdrant_url(configured: str | None) -> str | None:
    """The address to use on the host, or None to leave QDRANT_URL as it is."""
    return HOST_QDRANT_URL if urlparse(configured or "").hostname in (None, "qdrant") else None
