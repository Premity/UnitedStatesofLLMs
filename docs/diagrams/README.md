# Figures

Generated SVGs for the Phase 3 submission and the design docs. Each figure is
produced by a Python script in this directory — edit the script, not the SVG,
and regenerate.

```bash
make figures          # regenerate every SVG
```

Or individually:

```bash
cd docs/diagrams && python3 fig1_system_architecture.py
```

No dependencies beyond the standard library. `_svgkit.py` holds the shared
primitives — palette, type scale, arrowheads — so every figure reads as one
system; change it there rather than per-figure.

## The figures

| Figure | Script | Shows |
| --- | --- | --- |
| **1 — Component architecture** | [`fig0_component_stack.py`](fig0_component_stack.py) | Deployment view: every box a container with its port and image. The primary architecture figure |
| **2 — System architecture** | [`fig1_system_architecture.py`](fig1_system_architecture.py) | The same system arranged by data flow, opening up the `api` box |
| **3 — Debate workflow** | [`fig2_debate_flowchart.py`](fig2_debate_flowchart.py) | One request end to end, with both termination conditions |
| **4 — Module I/O** | [`fig3_module_io.py`](fig3_module_io.py) | Input / processing / output per module, plus the contract each must not break |

Script filenames keep their original numbering; the figure numbers above are
the ones used in the documents.

## What counts as a component

Figure 1 is a deployment view, so a box earns its place by being a deployment
unit — its own image, its own lifecycle, reached only through a declared
interface. That is why the four debate roles are *not* drawn as components:
they are modules inside the `api` container (ADR 0003), and drawing them as
boxes would misrepresent what is deployed. `council-core` appears only as the
base image, because that is how it ships.

## Converting for documents

SVG is the source format. Word does not place SVG reliably across versions, so
raster it first:

```bash
magick -density 160 -background white fig1-system-architecture.svg fig1.png
```

`-density 160` is the floor for print legibility; the 11pt labels go mushy
below about 130. For slides, 110 is enough.

## Routing rules

Long connectors run in reserved gutters outside the content bands, never
through them. When adding one, check the rendered PNG rather than trusting the
coordinates — a line that clips a label is the most common defect here, and it
is invisible in the source.

## Placeholders — figures not yet drawn

These are referenced in the design docs or likely to be wanted for the PRD, but
have no script yet. Each entry states what the figure must show, so it can be
drawn without rereading the whole design.

### Figure 4 — Deployment topology

**Status:** not drawn.

Three compose profiles side by side: dev (source bind-mounted, Vite HMR, ports
exposed), prod (baked images, nginx, memory caps), and the opt-in `ollama`
profile. Should show the shared `council-base` image beneath the Python
services and make the image sizes visible, since the point of the figure is
that one base layer is built once and reused.

### Figure 5 — Citation resolution state machine

**Status:** not drawn.

The four statuses as terminal states, with the decision path into each: locator
found or not → quote compared or not → similarity against τ. Must make the
`unresolved` / `out_of_corpus` split visually prominent, because collapsing
those two is the failure the figure exists to prevent.

### Figure 6 — Evaluation ablation ladder

**Status:** not drawn.

Five arms as rungs, each adding one capability over the one below: raw → rag →
single attacker → full council, with the compute-matched self-consistency
baseline drawn off to the side rather than on the ladder, since it is a
control, not a rung. Annotate each rung with the claim it isolates.

### Figure 7 — Sequence diagram, one debate round

**Status:** not drawn.

Lifelines for the orchestrator, the four roles, the resolver and the stores,
showing the concurrent attacker span explicitly as an overlapping region. The
architecture and flowchart both flatten that concurrency; this figure is where
it should be legible.
