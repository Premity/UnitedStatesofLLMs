"""Figure 1 — System architecture.

Four horizontal bands, read top to bottom: the user-facing client, the online
runtime that serves a debate, the shared library both other layers build on,
and the offline pipeline plus the model providers. Connectors are routed down
the right-hand gutter so no line crosses a band it does not touch.
"""

import os

from _svgkit import arrow, band, box, caption, footer, header, poly, text, write

W, H = 1250, 860
p = [header(W, H)]

p.append(
    text(
        W / 2,
        34,
        "United States of LLMs — System Architecture",
        fs=17,
        weight="700",
        anchor="middle",
    )
)
p.append(
    text(
        W / 2,
        53,
        "Adversarial multi-agent debate for international humanitarian law",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

# ── Client ────────────────────────────────────────────────────────────────
p.append(
    band(40, 74, 1060, 96, "CLIENT  ·  runtime/frontend  ·  React 18 + TypeScript", kind="accent")
)
p.append(box(70, 100, 215, 58, "Researcher", kind="plain", sub="poses question + facts"))
p.append(box(395, 100, 300, 58, "Courtroom View", kind="accent", sub="animated debate, live turns"))
p.append(
    box(755, 100, 315, 58, "Dissent Log View", kind="accent", sub="overruled objections, citations")
)

# ── Runtime ───────────────────────────────────────────────────────────────
p.append(
    band(40, 214, 1060, 310, "ONLINE RUNTIME  ·  runtime/api  ·  FastAPI + LangGraph", kind="local")
)

p.append(
    box(70, 250, 185, 68, "API Layer", kind="local", sub=["POST /api/debates", "SSE turn stream"])
)

# request down, stream back up — two separate lanes, clear of the boxes
p.append(poly([(150, 158), (150, 248)], label="question + facts", lx=142, ly=196, anchor="end"))
p.append(poly([(205, 248), (205, 160)], label="SSE", lx=213, ly=200, anchor="start", dark=True))

# Orchestrator
p.append(band(290, 240, 580, 210, "DEBATE ORCHESTRATOR  ·  StateGraph", kind="plain", dash=True))
p.append(box(308, 268, 108, 48, "retrieve", kind="plain", fs=12))
p.append(box(440, 268, 108, 48, "present", kind="plain", fs=12))
p.append(box(572, 250, 128, 40, ["attacker"], kind="plain", fs=11.5, sub="doctrinal"))
p.append(box(572, 300, 128, 40, ["attacker"], kind="plain", fs=11.5, sub="evidentiary"))
p.append(box(724, 268, 100, 48, "judge", kind="plain", fs=12))

p.append(arrow(416, 292, 438, 292))
p.append(arrow(548, 292, 570, 272))
p.append(arrow(548, 292, 570, 318))
p.append(arrow(700, 270, 722, 286))
p.append(arrow(700, 320, 722, 302))
p.append(
    poly(
        [(774, 316), (774, 360), (494, 360), (494, 318)],
        label="next round  ·  bounded by max_rounds",
        lx=634,
        ly=375,
    )
)

p.append(arrow(255, 284, 306, 284))

p.append(
    box(
        308,
        392,
        250,
        44,
        "Citation Resolver",
        kind="core",
        fs=12,
        sub="runs at every role boundary",
    )
)
p.append(text(576, 408, "resolved · unresolved", fs=10.5, fill="#6b6b6b"))
p.append(text(576, 422, "out_of_corpus · misquoted", fs=10.5, fill="#6b6b6b"))

# Stores, right column
p.append(box(900, 250, 180, 56, "Qdrant", kind="local", sub="vector store · ihl_corpus"))
p.append(box(900, 322, 180, 56, "Run Artifacts", kind="local", sub="data/runs/ · JSON"))
p.append(box(900, 394, 180, 44, "Citation Index", kind="local", fs=12, sub="locator → document"))

p.append(arrow(828, 268, 898, 268, "top-k"))
p.append(arrow(828, 300, 898, 338, "persist", lx=862, ly=330))
p.append(arrow(760, 414, 898, 414, "verify"))

# ── Shared library ────────────────────────────────────────────────────────
p.append(band(40, 546, 1060, 78, "SHARED LIBRARY  ·  packages/council-core", kind="core"))
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
    p.append(box(62 + i * 172, 572, 156, 42, lab, kind="core", fs=12, sub=sub))

p.append(poly([(230, 524), (230, 544)], dark=True))
p.append(text(243, 540, "imports", fs=10.5, fill="#6b6b6b"))

# ── Offline pipeline ──────────────────────────────────────────────────────
p.append(band(40, 652, 620, 104, "OFFLINE PIPELINE  ·  run to completion", kind="offline"))
p.append(box(62, 682, 140, 54, "Manifests", kind="offline", fs=12, sub="defines scope"))
p.append(box(238, 682, 140, 54, "Fetcher", kind="offline", fs=12, sub="never crawls"))
p.append(box(414, 682, 222, 54, "Indexer", kind="offline", fs=12, sub="chunk · embed · upsert"))
p.append(arrow(202, 709, 236, 709))
p.append(arrow(378, 709, 412, 709))

# ── Providers ─────────────────────────────────────────────────────────────
p.append(band(700, 652, 400, 104, "MODEL PROVIDERS", kind="external"))
p.append(box(722, 682, 112, 54, "Mistral", kind="external", fs=12, sub="presenter"))
p.append(box(850, 682, 112, 54, "Gemini", kind="external", fs=12, sub="judge"))
p.append(box(978, 682, 104, 54, "Ollama", kind="external", fs=12, sub="attackers ×2"))

# ── Right-hand gutter: the two long connectors ────────────────────────────
# indexer → stores (writes), routed outside every band
p.append(
    poly(
        [(638, 679), (1170, 679), (1170, 278), (1084, 278)],
        label="writes collection",
        lx=1162,
        ly=470,
        anchor="end",
    )
)
p.append(text(1162, 485, "+ citation index", fs=10.5, fill="#6b6b6b", anchor="end"))
p.append(poly([(1170, 416), (1084, 416)]))

# providers ↔ roles, via the left gutter
p.append(
    poly(
        [(778, 680), (778, 640), (20, 640), (20, 292), (306, 292)],
        label="LiteLLM gateway  ·  one call path for every role",
        lx=300,
        ly=634,
        anchor="start",
    )
)

p.append(
    caption(
        40,
        792,
        "The citation resolver sits on the role boundary, so arguments reach the judge "
        "already marked grounded or unsupported.",
    )
)
p.append(
    caption(
        40,
        810,
        "Both attackers execute concurrently and write to append-only state channels; "
        "every other channel has exactly one writer.",
    )
)
p.append(
    caption(
        40,
        828,
        "The pipeline runs offline and populates the stores the runtime reads. It is "
        "never on the request path.",
    )
)

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig1-system-architecture.svg"), p)
