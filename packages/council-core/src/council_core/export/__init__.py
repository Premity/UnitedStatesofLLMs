"""Renders a run artifact into reviewable documents.

The JSON artifact is the source of truth; these are the shareable views of it.
Markdown for reading and diffing, HTML for printing to PDF from a browser.
"""

from council_core.export.renderer import render_html, render_markdown

__all__ = ["render_html", "render_markdown"]
