"""System architecture — the data-flow view.

The same components as the stack figure, but arranged by how data moves rather
than by what sits on what. Reserved gutters keep every long connector clear of
the bands: nothing crosses a band it does not terminate in, and no line passes
through a label.

Layout budget
  x    0 to   70  left gutter: the model-gateway return path
  x   86 to 1120  content bands
  x 1140 to 1240  right gutter: the pipeline's write path
"""

import os

from _svgkit import arrow, band, box, caption, footer, header, poly, text, write

W, H = 1300, 900
p = [header(W, H)]

p.append(text(W / 2, 34, "System Architecture", fs=17, weight="700", anchor="middle"))
p.append(
    text(
        W / 2,
        53,
        "How data moves through the system during a single debate",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

BL, BW = 86, 1034  # band left edge and width

# ── Client ────────────────────────────────────────────────────────────────
p.append(
    band(BL, 76, BW, 100, "CLIENT  ·  runtime/frontend  ·  React 18 + TypeScript", kind="accent")
)
p.append(box(BL + 26, 104, 215, 60, "Researcher", kind="plain", sub="poses question + facts"))
p.append(
    box(BL + 320, 104, 300, 60, "Courtroom View", kind="accent", sub="animated debate, live turns")
)
p.append(
    box(
        BL + 672,
        104,
        320,
        60,
        "Dissent Log View",
        kind="accent",
        sub="overruled objections, citations",
    )
)

# ── Runtime ───────────────────────────────────────────────────────────────
RT_Y = 236
p.append(
    band(BL, RT_Y, BW, 330, "ONLINE RUNTIME  ·  runtime/api  ·  FastAPI + LangGraph", kind="local")
)

p.append(
    box(
        BL + 26,
        RT_Y + 42,
        190,
        70,
        "API Layer",
        kind="local",
        sub=["POST /api/debates", "SSE turn stream"],
    )
)

# Request down and stream up — two lanes with their labels outside the arrows.
p.append(poly([(BL + 78, 164), (BL + 78, RT_Y + 40)]))
p.append(text(BL + 70, 206, "question", fs=10.5, fill="#6b6b6b", anchor="end"))
p.append(text(BL + 70, 220, "+ facts", fs=10.5, fill="#6b6b6b", anchor="end"))
p.append(poly([(BL + 166, RT_Y + 40), (BL + 166, 166)], dark=True))
p.append(text(BL + 176, 212, "SSE", fs=10.5, fill="#6b6b6b", anchor="start"))

# ── Orchestrator ──────────────────────────────────────────────────────────
OX, OY = BL + 246, RT_Y + 30
p.append(band(OX, OY, 560, 216, "DEBATE ORCHESTRATOR  ·  StateGraph", kind="plain", dash=True))

p.append(box(OX + 20, OY + 34, 110, 50, "retrieve", kind="plain", fs=12))
p.append(box(OX + 156, OY + 34, 110, 50, "present", kind="plain", fs=12))
p.append(box(OX + 292, OY + 14, 132, 42, ["attacker"], kind="plain", fs=11.5, sub="doctrinal"))
p.append(box(OX + 292, OY + 66, 132, 42, ["attacker"], kind="plain", fs=11.5, sub="evidentiary"))
p.append(box(OX + 436, OY + 34, 104, 50, "judge", kind="plain", fs=12))

p.append(arrow(OX + 130, OY + 59, OX + 154, OY + 59))
p.append(arrow(OX + 266, OY + 59, OX + 290, OY + 37))
p.append(arrow(OX + 266, OY + 59, OX + 290, OY + 85))
p.append(arrow(OX + 424, OY + 35, OX + 434, OY + 52))
p.append(arrow(OX + 424, OY + 87, OX + 434, OY + 68))

# loop-back, routed below the node row with the label clear of the line
p.append(
    poly([(OX + 488, OY + 84), (OX + 488, OY + 132), (OX + 211, OY + 132), (OX + 211, OY + 86)])
)
p.append(
    text(
        OX + 358,
        OY + 148,
        "next round  ·  bounded by max_rounds",
        fs=10.5,
        fill="#6b6b6b",
        anchor="middle",
    )
)

p.append(arrow(BL + 216, RT_Y + 77, OX + 18, RT_Y + 77))

# Citation resolver, below the orchestrator band
p.append(
    box(
        OX + 20,
        OY + 168,
        260,
        46,
        "Citation Resolver",
        kind="core",
        fs=12,
        sub="runs at every role boundary",
    )
)
p.append(arrow(OX + 284, OY + 191, OX + 292, OY + 191))
p.append(text(OX + 300, OY + 178, "resolved · unresolved", fs=10.5, fill="#6b6b6b"))
p.append(text(OX + 300, OY + 192, "out_of_corpus · misquoted", fs=10.5, fill="#6b6b6b"))

# ── Stores, right column of the runtime band ──────────────────────────────
SX = BL + 874
p.append(box(SX, RT_Y + 42, 186, 58, "Qdrant", kind="local", sub="vector store · ihl_corpus"))
p.append(box(SX, RT_Y + 126, 186, 58, "Run Artifacts", kind="local", sub="data/runs/ · JSON"))
p.append(
    box(SX, RT_Y + 196, 186, 48, "Citation Index", kind="local", fs=12, sub="locator → document")
)

p.append(
    poly([(OX + 542, OY + 46), (OX + 610, OY + 46), (OX + 610, RT_Y + 62), (SX - 2, RT_Y + 62)])
)
p.append(text(OX + 618, RT_Y + 54, "top-k", fs=10.5, fill="#6b6b6b", anchor="start"))
p.append(
    poly([(OX + 542, OY + 72), (OX + 578, OY + 72), (OX + 578, RT_Y + 150), (SX - 2, RT_Y + 150)])
)
p.append(text(OX + 586, RT_Y + 142, "persist", fs=10.5, fill="#6b6b6b", anchor="start"))
p.append(poly([(OX + 470, OY + 191), (SX - 2, OY + 191)]))
p.append(text(OX + 500, OY + 183, "verify", fs=10.5, fill="#6b6b6b", anchor="start"))

# ── Shared library ────────────────────────────────────────────────────────
LIB_Y = 598
p.append(band(BL, LIB_Y, BW, 80, "SHARED LIBRARY  ·  packages/council-core", kind="core"))
for i, (lab, sub) in enumerate(
    [
        ("models/", "domain types"),
        ("llm/", "LiteLLM gateway"),
        ("citations/", "resolver"),
        ("prompts/", "versioned + hashed"),
        ("export/", "dissent log"),
        ("telemetry/", "structlog"),
    ]
):
    p.append(box(BL + 18 + i * 167, LIB_Y + 26, 151, 42, lab, kind="core", fs=12, sub=sub))

p.append(poly([(BL + 190, RT_Y + 330), (BL + 190, LIB_Y - 2)], dark=True))
p.append(text(BL + 202, LIB_Y - 10, "imports", fs=10.5, fill="#6b6b6b"))

# ── Offline pipeline ──────────────────────────────────────────────────────
PIPE_Y = 706
p.append(band(BL, PIPE_Y, 600, 104, "OFFLINE PIPELINE  ·  run to completion", kind="offline"))
p.append(
    box(BL + 18, PIPE_Y + 30, 140, 54, "Manifests", kind="offline", fs=12, sub="defines scope")
)
p.append(box(BL + 194, PIPE_Y + 30, 140, 54, "Fetcher", kind="offline", fs=12, sub="never crawls"))
p.append(
    box(
        BL + 370,
        PIPE_Y + 30,
        212,
        54,
        "Indexer",
        kind="offline",
        fs=12,
        sub="chunk · embed · upsert",
    )
)
p.append(arrow(BL + 158, PIPE_Y + 57, BL + 192, PIPE_Y + 57))
p.append(arrow(BL + 334, PIPE_Y + 57, BL + 368, PIPE_Y + 57))

# ── Providers ─────────────────────────────────────────────────────────────
PV_X = BL + 640
p.append(band(PV_X, PIPE_Y, 394, 104, "MODEL PROVIDERS", kind="external"))
p.append(box(PV_X + 20, PIPE_Y + 30, 112, 54, "Mistral", kind="external", fs=12, sub="presenter"))
p.append(box(PV_X + 146, PIPE_Y + 30, 112, 54, "Gemini", kind="external", fs=12, sub="judge"))
p.append(
    box(PV_X + 272, PIPE_Y + 30, 102, 54, "Ollama", kind="external", fs=12, sub="attackers ×2")
)

# ── Right gutter: pipeline writes the stores ──────────────────────────────
GR = 1176
p.append(poly([(BL + 600, PIPE_Y + 20), (GR, PIPE_Y + 20), (GR, RT_Y + 62), (SX + 188, RT_Y + 62)]))
p.append(poly([(GR, RT_Y + 220), (SX + 188, RT_Y + 220)]))
p.append(text(GR + 12, RT_Y + 140, "writes the", fs=10.5, fill="#6b6b6b", anchor="start"))
p.append(text(GR + 12, RT_Y + 154, "collection and", fs=10.5, fill="#6b6b6b", anchor="start"))
p.append(text(GR + 12, RT_Y + 168, "citation index", fs=10.5, fill="#6b6b6b", anchor="start"))

# ── Left gutter: one model call path ──────────────────────────────────────
GL = 44
p.append(
    poly(
        [
            (PV_X + 197, PIPE_Y),
            (PV_X + 197, PIPE_Y - 26),
            (GL, PIPE_Y - 26),
            (GL, RT_Y + 77),
            (BL + 24, RT_Y + 77),
        ]
    )
)
p.append(
    text(
        GL + 16,
        PIPE_Y - 12,
        "LiteLLM gateway  ·  one call path for every role",
        fs=10.5,
        fill="#6b6b6b",
        anchor="start",
    )
)

p.append(
    caption(
        BL,
        844,
        "The citation resolver sits on the role boundary, so arguments reach the judge already "
        "marked grounded or unsupported.",
    )
)
p.append(
    caption(
        BL,
        862,
        "Both attackers execute concurrently and write to append-only state channels; every "
        "other channel has exactly one writer.",
    )
)
p.append(
    caption(
        BL,
        880,
        "The pipeline runs offline and populates the stores the runtime reads. It is never on "
        "the request path.",
    )
)

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig1-system-architecture.svg"), p)
