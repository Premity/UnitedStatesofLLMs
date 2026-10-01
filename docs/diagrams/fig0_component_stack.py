"""Figure 1 — Component architecture (deployment view).

Components are *deployment units* — things that start, stop and are versioned
independently. Each box is one such unit, annotated with the port it listens on
and the image it is built from.

The layout carries the central structural claim: the offline pipeline and the
online runtime are separate regions that never run at the same time, and they
communicate only through the datastores drawn between them. The pipeline writes
those stores; the runtime reads them.
"""

import os

from _svgkit import arrow, caption, footer, header, poly, region, text, unit, write

W, H = 1270, 1090
p = [header(W, H)]

p.append(text(W / 2, 34, "Figure 1 — Component Architecture", fs=18, weight="700", anchor="middle"))
p.append(
    text(
        W / 2,
        54,
        "Every box is a deployment unit: its own container, image and lifecycle",
        fs=12,
        fill="#6b6b6b",
        anchor="middle",
    )
)

# ══ OFFLINE PIPELINE ══════════════════════════════════════════════════════
PY0 = 86
p.append(
    region(
        56,
        PY0,
        1158,
        342,
        "OFFLINE PIPELINE  ·  pipeline/docker-compose.yml  ·  run to completion",
        kind="offline",
    )
)

# external sources feeding the fetcher
p.append(text(96, PY0 + 40, "ICRC Treaty Database", fs=11.5, weight="600"))
p.append(text(96, PY0 + 55, "ihl-databases.icrc.org", fs=10, fill="#6b6b6b", mono=True))
p.append(text(352, PY0 + 40, "ICC · ICJ · ICTY", fs=11.5, weight="600"))
p.append(text(352, PY0 + 55, "named decisions only", fs=10, fill="#6b6b6b", mono=True))
p.append(text(596, PY0 + 40, "UN Digital Library", fs=11.5, weight="600"))
p.append(text(596, PY0 + 55, "General Assembly resolutions", fs=10, fill="#6b6b6b", mono=True))

p.append(poly([(150, PY0 + 62), (150, PY0 + 92)]))
p.append(poly([(404, PY0 + 62), (404, PY0 + 92)]))
p.append(poly([(650, PY0 + 62), (650, PY0 + 92)]))
p.append(
    text(
        820,
        PY0 + 80,
        "fetched only if named in a manifest — the fetcher never crawls",
        fs=10.5,
        fill="#6b6b6b",
    )
)

p.append(
    unit(
        86,
        PY0 + 92,
        1068,
        76,
        "FETCHER",
        "council-fetcher  ·  FROM council-base",
        [
            "manifest-scoped download: corpus/manifests/{treaties,cases,resolutions}.json",
            "Tier 1 instruments committed to the repo · Tier 2 fetched · Tier 3 never indexed",
        ],
        kind="offline",
    )
)

p.append(poly([(620, PY0 + 168), (620, PY0 + 190)]))
p.append(text(636, PY0 + 184, "data/cache/  — raw documents on disk", fs=10.5, fill="#6b6b6b"))

p.append(
    unit(
        86,
        PY0 + 196,
        1068,
        104,
        "INDEXER",
        "council-indexer  ·  FROM council-base",
        [
            "1  chunk at citation granularity — treaty article, judgment paragraph",
            "2  embed with BGE-M3 via fastembed (ONNX runtime, no PyTorch)",
            "3  upsert vectors into the Qdrant collection",
            "4  write the citation index the resolver reads at runtime",
        ],
        kind="offline",
    )
)

# ══ DATASTORES — between the two regions ══════════════════════════════════
DS = PY0 + 352
p.append(poly([(330, PY0 + 300), (330, DS - 2)]))
p.append(poly([(900, PY0 + 300), (900, DS - 2)]))

p.append(
    unit(
        150,
        DS,
        360,
        92,
        "Qdrant",
        ":6333  ·  v1.12.4",
        [
            "collection ihl_corpus",
            "BGE-M3 dense vectors, cosine",
            "volume qdrant_data",
        ],
        kind="local",
    )
)
p.append(
    unit(
        730,
        DS,
        360,
        92,
        "Filesystem",
        "bind mount",
        [
            "citation index — locator → source text",
            "data/runs/ — one JSON artifact per run",
            "written even when a debate fails",
        ],
        kind="local",
    )
)

p.append(text(548, DS + 36, "the only channel", fs=10.5, fill="#6b6b6b", anchor="middle"))
p.append(text(548, DS + 50, "between the two", fs=10.5, fill="#6b6b6b", anchor="middle"))
p.append(text(548, DS + 64, "regions", fs=10.5, fill="#6b6b6b", anchor="middle"))

# ══ RUNTIME STACK ═════════════════════════════════════════════════════════
RY = DS + 148
p.append(
    region(
        56,
        RY,
        1158,
        330,
        "RUNTIME STACK  ·  docker-compose.yml  ·  serves one debate at a time",
        kind="local",
    )
)

p.append(poly([(330, DS + 94), (330, RY + 40)], dark=True))
p.append(text(342, DS + 126, "read: top-k retrieval", fs=10.5, fill="#6b6b6b"))
p.append(poly([(900, DS + 94), (900, RY + 40)], dark=True))
p.append(text(760, DS + 126, "read + write: citations, runs", fs=10.5, fill="#6b6b6b"))

p.append(
    unit(
        86,
        RY + 40,
        740,
        116,
        "api",
        ":8000  ·  council-api 924 MB  ·  FROM council-base",
        [
            "FastAPI + LangGraph StateGraph, compiled once at import",
            "roles as modules: presenter · attacker ×2 · judge — not four services",
            "citation resolver invoked at every role boundary",
            "SSE turn-level stream (POST body, so not EventSource)",
        ],
        kind="local",
    )
)

p.append(
    unit(
        860,
        RY + 40,
        280,
        116,
        "ollama",
        ":11434",
        [
            "host by default",
            "opt-in compose profile",
            "qwen3.5:14b — doctrinal",
            "gemma3:12b — evidentiary",
        ],
        kind="external",
    )
)
p.append(arrow(828, RY + 84, 858, RY + 84))
p.append(text(760, RY + 176, "host.docker.internal", fs=10, fill="#6b6b6b", mono=True))

p.append(
    unit(
        86,
        RY + 196,
        740,
        104,
        "frontend",
        ":3000 dev · :80 prod  ·  council-frontend 375 MB",
        [
            "React 18 + TypeScript + Vite 6 + Tailwind + Zustand",
            "courtroom view — Framer Motion, sprites enact the debate turn by turn",
            "dissent log view — overruled objections with the judge's reason",
            "dev: Vite HMR with source bind-mounted · prod: static build behind nginx",
        ],
        kind="accent",
    )
)
p.append(poly([(456, RY + 158), (456, RY + 194)], dark=True))
p.append(text(468, RY + 180, "SSE", fs=10.5, fill="#6b6b6b"))

p.append(
    unit(
        860,
        RY + 196,
        280,
        104,
        "council-base",
        "578 MB",
        [
            "python:3.12-slim",
            "uv + pinned runtime",
            "council-core installed",
            "built once, shared by",
            "api · fetcher · indexer",
        ],
        kind="core",
    )
)
p.append(poly([(998, RY + 194), (998, RY + 160)]))
p.append(text(1010, RY + 180, "FROM", fs=10, fill="#6b6b6b", mono=True))

# ══ External model providers ══════════════════════════════════════════════
EY = RY + 352
p.append(text(86, EY + 4, "EXTERNAL MODEL PROVIDERS", fs=11.5, weight="700", fill="#5b7fa6"))
p.append(
    unit(
        86,
        EY + 14,
        520,
        62,
        "Mistral  ·  magistral-medium",
        "presenter  ·  free tier",
        ["builds the position — sets the quality ceiling for the debate"],
        kind="external",
        fs=12,
    )
)
p.append(
    unit(
        634,
        EY + 14,
        520,
        62,
        "Google AI Studio  ·  gemini-2.5-pro",
        "judge  ·  100 req/day",
        ["rules on every objection, calibrates confidence — the binding quota"],
        kind="external",
        fs=12,
    )
)
p.append(poly([(346, EY + 12), (346, EY - 10), (26, EY - 10), (26, RY + 98), (84, RY + 98)]))
p.append(
    text(
        360,
        EY - 14,
        "LiteLLM gateway — one call path for every role",
        fs=10.5,
        fill="#6b6b6b",
    )
)

p.append(
    caption(
        56,
        H - 42,
        "The two regions have separate compose files and never run at the same time. The "
        "pipeline produces the stores; the runtime consumes them. Re-run the pipeline only "
        "when the corpus changes.",
    )
)
p.append(
    caption(
        56,
        H - 24,
        "Roles are modules inside the api container, not separate services: the debate is "
        "sequential, so four containers would buy network hops and nothing else (ADR 0003).",
    )
)

p.append(footer())
write(os.path.join(os.path.dirname(__file__), "fig0-component-stack.svg"), p)
