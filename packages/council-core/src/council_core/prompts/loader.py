"""Loads and renders prompt templates from the `prompts/` directory.

Prompts live in files, not string literals, for three reasons: changing one is a
reviewable diff; the same template can be rendered for four different models;
and the template hash goes into the run artifact, so a result can never be
silently attributed to a prompt that has since changed.

Layout is `prompts/<role>/<name>.md`, addressed as `<role>/<name>`. A template
may declare an optional `---`-fenced YAML-ish header with a `system:` block; if
absent, the shared system prompt for the role is used.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, StrictUndefined

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RenderedPrompt:
    """A prompt ready to send, with the provenance needed to reproduce it."""

    prompt_id: str
    system: str
    user: str
    template_hash: str
    """SHA-256 of the raw template source, before rendering."""

    rendered_hash: str
    """SHA-256 of the rendered text. Differs per run; identifies this exact call."""


class PromptLoader:
    """Renders prompt templates for a role.

    Templates are cached after first read. In dev the API runs with reload
    enabled, so editing a prompt and refreshing picks up the change.
    """

    def __init__(self, prompts_dir: Path) -> None:
        self._dir = prompts_dir
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,  # a missing variable is a bug, not a blank
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # prompts are plain text, not markup
        )

    def render(
        self,
        prompt_id: str,
        *,
        system_id: str | None = None,
        **context: Any,
    ) -> RenderedPrompt:
        """Render `prompts/<prompt_id>.md` with `context`.

        Args:
            prompt_id: Template path without extension, e.g. `presenter/opening`.
            system_id: System prompt to pair with it. Defaults to
                `shared/<role>_system` where role is the first path segment.
            **context: Template variables. A missing one raises rather than
                rendering an empty string.
        """
        role = prompt_id.split("/", 1)[0]
        system_id = system_id or f"shared/{role}_system"

        user_source = self._source(prompt_id)
        system_source = self._source(system_id)

        user = self._env.get_template(f"{prompt_id}.md").render(**context)
        system = self._env.get_template(f"{system_id}.md").render(**context)

        return RenderedPrompt(
            prompt_id=prompt_id,
            system=system,
            user=user,
            template_hash=_sha256(system_source + user_source),
            rendered_hash=_sha256(system + user),
        )

    @lru_cache(maxsize=64)  # noqa: B019  — loader is a long-lived singleton
    def _source(self, prompt_id: str) -> str:
        path = self._dir / f"{prompt_id}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
