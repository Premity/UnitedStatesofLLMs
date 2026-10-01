"""Figure 3 — Module input/processing/output.

One row per major module. Reads left to right: what the module receives, what
it does with it, what it hands on. The right-hand column names the contract the
module must not break — the constraints that fail silently rather than loudly.
"""

import os

from _svgkit import FILLS, STROKES, caption, footer, header, text, write

W = 1200
ROW_H = 76
TOP = 128
ROWS = [
    (
        "Retriever",
        "runtime/api",
        ["question + facts", "top_k (1–50)"],
        ["embed query (BGE-M3, ONNX)", "cosine search over ihl_corpus"],
        ["ranked passages", "each with a locator"],
        "Query embedding model must match the indexer's",
    ),
    (
        "Presenter",
        "roles/presenter",
        ["question + facts", "retrieved passages", "prior objections"],
        ["build the position", "rebut in later rounds"],
        ["Argument[]", "each with Citation[]"],
        "Sets the quality ceiling — attackers can only test the case given",
    ),
    (
        "Doctrinal attacker",
        "roles/attacker",
        ["arguments", "retrieved passages"],
        ["attack legal characterisation:", "tests, elements, interpretation"],
        ["Objection[]", "raised_by = doctrinal"],
        "Must leave factual sufficiency to its counterpart",
    ),
    (
        "Evidentiary attacker",
        "roles/attacker",
        ["arguments", "retrieved passages"],
        ["attack the factual predicate:", "sufficiency, mens rea, attribution"],
        ["Objection[]", "raised_by = evidentiary"],
        "Runs concurrently; writes only append-only channels",
    ),
    (
        "Citation resolver",
        "council-core",
        ["Citation[] from a role", "citation index"],
        ["look up locator", "fuzzy-match quote (τ = 0.6)"],
        ["ResolvedCitation[]", "one of four statuses"],
        "unresolved ≠ out_of_corpus — merging them voids the fabrication metric",
    ),
    (
        "Judge",
        "roles/judge",
        ["arguments + objections", "with citation statuses"],
        ["rule on every objection", "price residual uncertainty"],
        ["Verdict", "confidence ∈ [0,1]"],
        "Must rule on every objection — silence is not a ruling",
    ),
    (
        "Orchestrator",
        "graph/workflow",
        ["DebateConfig", "GraphState"],
        ["sequence roles", "apply termination rules"],
        ["completed debate", "turn stream"],
        "max_rounds is an absolute ceiling in every mode",
    ),
    (
        "Exporter",
        "council-core",
        ["completed run artifact"],
        ["render dissent log", "resolve citations for display"],
        ["reviewable document", "Markdown / JSON"],
        "Overruled objections are the deliverable, not an appendix",
    ),
]

H = TOP + len(ROWS) * ROW_H + 96
p = [header(W, H)]

p.append(
    text(
        W / 2,
        34,
        "Figure 3 — Module Input, Processing and Output",
        fs=17,
        weight="700",
        anchor="middle",
    )
)
p.append(
    text(
        W / 2,
        53,
        "Each row is one module; the final column is the contract it must not break",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

COLS = [(40, 190), (240, 230), (480, 250), (740, 200), (950, 210)]
HEADS = ["MODULE", "INPUT", "PROCESSING", "OUTPUT", "MUST NOT BREAK"]

for (x, _w), h in zip(COLS, HEADS, strict=True):
    p.append(text(x + 10, TOP - 12, h, fs=10.5, weight="700", fill="#5b7fa6", anchor="start"))

p.append(
    f'<line x1="40" y1="{TOP - 4}" x2="{W - 40}" y2="{TOP - 4}" '
    f'stroke="#5b7fa6" stroke-width="1.2"/>\n'
)

for i, (name, path, inp, proc, outp, guard) in enumerate(ROWS):
    y = TOP + i * ROW_H
    if i % 2 == 0:
        p.append(f'<rect x="40" y="{y}" width="{W - 80}" height="{ROW_H}" fill="#f7f8fa"/>\n')

    # module name + path
    p.append(text(COLS[0][0] + 10, y + 28, name, fs=13, weight="700"))
    p.append(text(COLS[0][0] + 10, y + 45, path, fs=10.5, fill="#6b6b6b", mono=True))

    for (cx, cw), lines, kind in (
        (COLS[1], inp, "external"),
        (COLS[2], proc, "local"),
        (COLS[3], outp, "core"),
    ):
        p.append(
            f'<rect x="{cx}" y="{y + 10}" width="{cw}" height="{ROW_H - 20}" rx="3" '
            f'fill="{FILLS[kind]}" stroke="{STROKES[kind]}" stroke-width="0.9"/>\n'
        )
        ty = y + ROW_H / 2 - (len(lines) - 1) * 7
        for ln in lines:
            p.append(text(cx + 10, ty, ln, fs=11))
            ty += 14

    # guard column — plain text, no box, so it reads as annotation
    gy = y + ROW_H / 2 - 4
    words, line, wrapped = guard.split(), "", []
    for wd in words:
        if len(line + " " + wd) > 34:
            wrapped.append(line)
            line = wd
        else:
            line = (line + " " + wd).strip()
    wrapped.append(line)
    gy = y + ROW_H / 2 - (len(wrapped) - 1) * 7
    for ln in wrapped:
        p.append(text(COLS[4][0] + 6, gy, ln, fs=10.5, fill="#6b6b6b"))
        gy += 14

    p.append(
        f'<line x1="40" y1="{y + ROW_H}" x2="{W - 40}" y2="{y + ROW_H}" '
        f'stroke="#dcdcdc" stroke-width="0.8"/>\n'
    )

base = TOP + len(ROWS) * ROW_H
p.append(
    caption(
        40,
        base + 28,
        "The two attackers share one implementation class, differing only by prompt "
        "template and model, so disabling one changes nothing about the other.",
    )
)
p.append(
    caption(
        40,
        base + 46,
        "raised_by is overwritten with the true role after parsing, so a model cannot "
        "attribute objections to its counterpart and distort the independence metric.",
    )
)
p.append(
    caption(
        40,
        base + 64,
        "Every module's output is validated against a schema before the next module "
        "sees it; a parse failure is retried once with the validation error attached.",
    )
)

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig3-module-io.svg"), p)
