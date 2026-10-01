"""Figure 1 — Component stack.

Every component in the system, arranged as tiers. Read top to bottom: each tier
sits on the one beneath it. The point of this figure is what the system is
*made of* and what talks to what — the runtime flow is Figure 2's job.

Deliberately no crossing connectors. Tier-to-tier relationships are shown by
vertical adjacency and by short arrows in the gutters between tiers, so nothing
has to be traced across the page.
"""

import os

from _svgkit import FILLS, STROKES, arrow, box, caption, esc, footer, header, text, write

W, H = 1200, 1000
p = [header(W, H)]

p.append(text(W / 2, 36, "Figure 1 — Component Stack", fs=18, weight="700", anchor="middle"))
p.append(
    text(
        W / 2,
        56,
        "What the system is built from. Each tier runs on the tier below it.",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

LEFT = 150
RIGHT = 1160
TIER_W = RIGHT - LEFT


def tier(y, h, label, sublabel, kind, boxes, gap=14):
    """One horizontal tier: a left-hand label and a row of component boxes."""
    out = [
        f'<rect x="{LEFT}" y="{y}" width="{TIER_W}" height="{h}" rx="6" '
        f'fill="{FILLS[kind]}" fill-opacity="0.5" stroke="{STROKES[kind]}" '
        f'stroke-width="1.3"/>\n'
    ]
    # left-hand tier label, outside the band
    out.append(
        f'<text x="{LEFT - 16}" y="{y + h / 2 - 3}" text-anchor="end" font-size="12.5" '
        f'font-weight="700" fill="{STROKES[kind]}">{esc(label)}</text>\n'
    )
    out.append(
        f'<text x="{LEFT - 16}" y="{y + h / 2 + 13}" text-anchor="end" font-size="10.5" '
        f'fill="#6b6b6b">{esc(sublabel)}</text>\n'
    )

    n = len(boxes)
    inner = TIER_W - 28
    bw = (inner - gap * (n - 1)) / n
    for i, (title, sub) in enumerate(boxes):
        bx = LEFT + 14 + i * (bw + gap)
        out.append(box(bx, y + 13, bw, h - 26, title, kind=kind, sub=sub, fs=12.5))
    return "".join(out)


# ── Tier 1: client ────────────────────────────────────────────────────────
p.append(
    tier(
        82,
        86,
        "PRESENTATION",
        "user's browser",
        "accent",
        [
            ("Courtroom view", ["React 18 · TypeScript", "Framer Motion"]),
            ("Dissent log view", ["overruled objections", "citation inspection"]),
            ("nginx", ["static build", "prod only"]),
        ],
    )
)
p.append(arrow(655, 168, 655, 196, "HTTP · POST + SSE", lx=665, ly=186, anchor="start"))

# ── Tier 2: API ───────────────────────────────────────────────────────────
p.append(
    tier(
        196,
        84,
        "SERVICE",
        "runtime/api",
        "local",
        [
            ("FastAPI", ["HTTP surface", "request validation"]),
            ("SSE stream", ["sse-starlette", "turn-level events"]),
            ("Uvicorn", ["ASGI server"]),
        ],
    )
)
p.append(arrow(655, 280, 655, 306))

# ── Tier 3: orchestration ─────────────────────────────────────────────────
p.append(
    tier(
        306,
        84,
        "ORCHESTRATION",
        "the debate graph",
        "local",
        [
            ("LangGraph StateGraph", ["concurrent nodes", "conditional loop edge"]),
            ("Round control", ["auto / fixed", "max_rounds ceiling"]),
            ("Run persistence", ["JSON artifacts", "written on failure too"]),
        ],
    )
)
p.append(arrow(655, 390, 655, 416))

# ── Tier 4: roles ─────────────────────────────────────────────────────────
p.append(
    tier(
        416,
        86,
        "ROLES",
        "modules, not services",
        "local",
        [
            ("Presenter", ["builds the case"]),
            ("Attacker — doctrinal", ["legal characterisation"]),
            ("Attacker — evidentiary", ["factual predicate"]),
            ("Judge", ["rules + calibrates"]),
        ],
    )
)
p.append(arrow(655, 502, 655, 528))

# ── Tier 5: domain library ────────────────────────────────────────────────
p.append(
    tier(
        528,
        86,
        "DOMAIN",
        "packages/council-core",
        "core",
        [
            ("Pydantic models", ["typed contracts"]),
            ("Citation resolver", ["4 statuses"]),
            ("Prompt loader", ["versioned + hashed"]),
            ("Exporters", ["dissent log"]),
        ],
    )
)
p.append(arrow(430, 614, 430, 640))
p.append(arrow(880, 614, 880, 640))

# ── Tier 6: gateway + embeddings ──────────────────────────────────────────
p.append(
    tier(
        640,
        80,
        "INTEGRATION",
        "one call path",
        "core",
        [
            ("LiteLLM gateway", ["structured output + repair retry"]),
            ("fastembed · ONNX", ["BGE-M3 · no PyTorch"]),
        ],
    )
)
p.append(arrow(430, 720, 430, 746))
p.append(arrow(880, 720, 880, 746))

# ── Tier 7: stores and providers ──────────────────────────────────────────
p.append(
    tier(
        746,
        86,
        "INFRASTRUCTURE",
        "state and models",
        "external",
        [
            ("Qdrant v1.12.4", ["ihl_corpus collection"]),
            ("Filesystem", ["data/runs · citation index"]),
            ("Mistral · Gemini", ["hosted APIs"]),
            ("Ollama", ["Qwen 3.5 · Gemma 3", "local"]),
        ],
    )
)

# ── Offline pipeline, set apart ───────────────────────────────────────────
p.append(
    tier(
        862,
        76,
        "PIPELINE",
        "offline, run to completion",
        "offline",
        [
            ("Manifests", ["defines corpus scope"]),
            ("Fetcher", ["never crawls"]),
            ("Indexer", ["chunk · embed · upsert"]),
        ],
    )
)
p.append(arrow(655, 862, 655, 836, "writes the stores above", lx=665, ly=852, anchor="start"))

p.append(
    caption(
        LEFT,
        962,
        "Every tier depends only on the tier beneath it. council-core imports nothing from "
        "the services above it, so the domain model is testable without Qdrant or a model call.",
    )
)
p.append(
    caption(
        LEFT,
        980,
        "The pipeline is drawn apart because it never runs during a request — it populates the "
        "infrastructure tier ahead of time.",
    )
)

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig0-component-stack.svg"), p)
