"""Dissent-log renderers.

A run artifact is a nested JSON object — correct, but not something you hand to
a supervisor. These renderers turn one into a document with the structure a
reader expects: the question, the holding and its confidence, the arguments that
survived, and then the dissent — every objection the judge overruled, with the
reason it was overruled and the authority each side relied on.

Unresolved citations are marked inline rather than dropped. A reader must be
able to see where the model reached for authority that does not exist.
"""

from __future__ import annotations

from council_core.models.citation import CitationStatus, ResolvedCitation
from council_core.models.debate import ObjectionDisposition
from council_core.models.run import RunArtifact

_STATUS_MARK = {
    CitationStatus.RESOLVED: "",
    CitationStatus.UNRESOLVED: " **[UNRESOLVED — not found in corpus]**",
    CitationStatus.OUT_OF_CORPUS: " *[outside indexed corpus — unverified]*",
    CitationStatus.MISQUOTED: " **[MISQUOTED — text does not match source]**",
}


def _cite_line(rc: ResolvedCitation) -> str:
    """One citation as a markdown list item, carrying its resolution status."""
    return f"- `{rc.citation.locator()}`{_STATUS_MARK[rc.status]}"


def render_markdown(artifact: RunArtifact) -> str:
    """Render a full dissent log as Markdown."""
    state = artifact.state
    meta = artifact.metadata
    out: list[str] = []

    out.append("# Dissent Log")
    out.append("")
    out.append(f"**Run:** `{meta.run_id}`  ")
    out.append(f"**Completed:** {meta.completed_at or '—'}  ")
    out.append(f"**Rounds:** {state.current_round} ({state.terminated_reason or 'n/a'})")
    out.append("")

    out.append("## Question")
    out.append("")
    out.append(state.config.question)
    if state.config.facts:
        out.append("")
        out.append("### Facts as given")
        out.append("")
        out.append(state.config.facts)
    out.append("")

    if state.verdict is None:
        out.append("## Verdict")
        out.append("")
        out.append("*No verdict — the debate did not complete.*")
        if meta.error:
            out.append("")
            out.append(f"**Error:** {meta.error}")
        return "\n".join(out)

    verdict = state.verdict

    out.append("## Holding")
    out.append("")
    out.append(verdict.conclusion)
    out.append("")
    out.append(f"**Confidence:** {verdict.confidence:.0%}")
    if verdict.confidence_reasoning:
        out.append("")
        out.append(f"> {verdict.confidence_reasoning}")
    out.append("")
    out.append("### Reasoning")
    out.append("")
    out.append(verdict.reasoning)
    out.append("")

    surviving = [a for a in state.arguments if a.id in verdict.surviving_argument_ids]
    if surviving:
        out.append("## Surviving arguments")
        out.append("")
        for i, arg in enumerate(surviving, 1):
            out.append(f"### {i}. {arg.claim}")
            out.append("")
            out.append(arg.reasoning)
            if arg.resolved_citations:
                out.append("")
                out.append("**Authority:**")
                out.extend(_cite_line(rc) for rc in arg.resolved_citations)
            out.append("")

    out.append("## Dissent — objections overruled")
    out.append("")
    if not verdict.dissent:
        out.append("*No objections were overruled.*")
        out.append("")
    else:
        out.append(
            "The following challenges were raised and rejected. They are recorded "
            "so that the reasoning behind the holding can be reviewed against the "
            "strongest arguments it had to survive."
        )
        out.append("")
        for i, obj in enumerate(verdict.dissent, 1):
            target = next((a for a in state.arguments if a.id == obj.target_argument_id), None)
            out.append(f"### {i}. {obj.ground}")
            out.append("")
            out.append(f"**Raised by:** {obj.raised_by.value.replace('_', ' ').title()}  ")
            if target:
                out.append(f"**Against:** {target.claim}")
            out.append("")
            out.append(obj.reasoning)
            if obj.resolved_citations:
                out.append("")
                out.append("**Authority relied on:**")
                out.extend(_cite_line(rc) for rc in obj.resolved_citations)
            out.append("")
            out.append(f"**Overruled because:** {obj.disposition_reasoning or '—'}")
            out.append("")

    sustained = [o for o in state.objections if o.disposition == ObjectionDisposition.SUSTAINED]
    if sustained:
        out.append("## Objections sustained")
        out.append("")
        for obj in sustained:
            out.append(f"- **{obj.ground}** — {obj.disposition_reasoning or '—'}")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Provenance")
    out.append("")
    out.append("| Role | Model |")
    out.append("| --- | --- |")
    for role, model in meta.role_models.items():
        out.append(f"| {role.replace('_', ' ').title()} | `{model}` |")
    out.append("")
    out.append(
        f"Tokens: {meta.total_prompt_tokens:,} prompt / "
        f"{meta.total_completion_tokens:,} completion. "
        f"Corpus `{meta.corpus_version or 'unknown'}`. "
        f"Council v{meta.council_version}."
    )
    out.append("")
    out.append("*Generated by an automated research system. Not legal advice; see DISCLAIMER.md.*")

    return "\n".join(out)


def render_html(artifact: RunArtifact) -> str:
    """Render a print-ready HTML document.

    Deliberately self-contained and dependency-free so it can be opened
    anywhere and printed to PDF from the browser.
    """
    import html as _html
    from xml.sax.saxutils import escape  # noqa: F401  (kept for callers extending this)

    md = render_markdown(artifact)
    body = _html.escape(md)
    title = f"Dissent Log — {artifact.metadata.run_id}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_html.escape(title)}</title>
<style>
  @page {{ margin: 2cm; }}
  body {{
    font: 11pt/1.6 Georgia, "Times New Roman", serif;
    max-width: 46em; margin: 3rem auto; padding: 0 1.5rem; color: #1a1a1a;
  }}
  pre {{ white-space: pre-wrap; font: inherit; }}
</style>
</head>
<body>
<pre>{body}</pre>
</body>
</html>
"""
