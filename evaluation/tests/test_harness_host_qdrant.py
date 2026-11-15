"""On the host, the harness must reach Qdrant on localhost (found in #25).

`.env` holds Qdrant's address inside the compose network, which the host
cannot resolve. Arms B-E then failed at retrieval while arm A succeeded. Each
test imports the harness in a fresh process, as `make eval` does, from a
directory whose `.env` holds the in-network address.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.host import host_qdrant_url

PROBE = (
    "import harness.run\n"
    "from app.core.config import Settings\n"
    "print('QDRANT_URL=' + Settings().qdrant_url)\n"
)

in_container = pytest.mark.skipif(
    Path("/data").exists(), reason="inside the container the in-network address is right"
)


def _qdrant_url_seen_by_the_harness(cwd: Path, **env: str) -> str:
    base = {k: v for k, v in os.environ.items() if k != "QDRANT_URL"}
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=cwd,
        env={**base, **env},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    line = next(x for x in result.stdout.splitlines() if x.startswith("QDRANT_URL="))
    return line.removeprefix("QDRANT_URL=")


@in_container
def test_the_harness_replaces_the_in_network_address_from_dotenv(tmp_path: Path) -> None:
    """End to end, in a fresh process: `.env` is loaded into os.environ during the
    harness's own imports, so only a real import shows the address it ends up with."""
    (tmp_path / ".env").write_text("QDRANT_URL=http://qdrant:6333\n")
    assert _qdrant_url_seen_by_the_harness(tmp_path) == "http://localhost:6333"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("http://qdrant:6333", "http://localhost:6333"),  # .env, and the app default
        (None, "http://localhost:6333"),
        ("", "http://localhost:6333"),
        ("http://localhost:6333", None),  # already right: left alone
        ("http://elsewhere:6333", None),  # an explicit address: left alone
    ],
)
def test_host_qdrant_url(configured: str | None, expected: str | None) -> None:
    assert host_qdrant_url(configured) == expected
