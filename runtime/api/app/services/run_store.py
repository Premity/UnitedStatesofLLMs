"""Persists run artifacts as JSON on disk.

One directory per run under `data/runs/<run_id>/`:

    artifact.json     the complete record — source of truth
    dissent.md        rendered dissent log
    dissent.html      print-ready version

Flat files rather than a database because the evaluation harness reads runs in
bulk and nothing queries across them at runtime. See
`docs/adr/0005-json-run-artifacts.md`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import structlog

from app.core.config import get_settings
from council_core.export import render_html, render_markdown
from council_core.models.run import RunArtifact, RunStatus

log = structlog.get_logger(__name__)


class RunStore:
    """Reads and writes run artifacts."""

    def __init__(self, runs_dir: Path) -> None:
        self._dir = runs_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        """Directory holding one run's files."""
        return self._dir / run_id

    def save(self, artifact: RunArtifact) -> Path:
        """Write the artifact and both rendered exports."""
        run_dir = self.path_for(artifact.metadata.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        (run_dir / "artifact.json").write_text(artifact.to_json(), encoding="utf-8")

        # Exports are only meaningful once there is a verdict to render.
        if artifact.metadata.status == RunStatus.COMPLETED:
            (run_dir / "dissent.md").write_text(render_markdown(artifact), encoding="utf-8")
            (run_dir / "dissent.html").write_text(render_html(artifact), encoding="utf-8")

        log.info("run_saved", run_id=artifact.metadata.run_id, path=str(run_dir))
        return run_dir

    def load(self, run_id: str) -> RunArtifact | None:
        """Read one artifact, or None if it does not exist."""
        path = self.path_for(run_id) / "artifact.json"
        if not path.exists():
            return None
        return RunArtifact.from_json(path.read_text(encoding="utf-8"))

    def list_runs(self, *, limit: int = 50) -> list[RunArtifact]:
        """Most recent runs first."""
        artifacts: list[RunArtifact] = []
        for path in sorted(
            self._dir.glob("*/artifact.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]:
            try:
                artifacts.append(RunArtifact.from_json(path.read_text(encoding="utf-8")))
            except Exception as exc:
                log.warning("run_unreadable", path=str(path), error=str(exc))
        return artifacts


@lru_cache
def get_run_store() -> RunStore:
    """Cached store singleton."""
    return RunStore(get_settings().runs_dir)
