# Architecture

How the system is put together and why it is shaped this way. For the reasoning
behind individual decisions, see [adr/](adr/); for the formal system-design
reference — requirements, contracts, failure modes, capacity — see
[system-design.md](system-design.md).

---

## The shape of the problem

A single LLM pass over a contested legal question produces a fluent, confident,
often wrong answer. The failure is structural: nothing in a single pass asks the
model to find the strongest response to its own argument, so it does not.

The system replaces the single pass with a proceeding. Four models, four
mandates, one record.

```
                      ┌─ attacker: doctrinal ──┐
retrieve → present ───┤                        ├──→ judge ──→ dissent log
    ↑                 └─ attacker: evidentiary ┘        │
    └──────────────── next round (if any) ──────────────┘
```

---

## Components

**A component is a deployment unit:** its own container image, its own
lifecycle, and a boundary other components cross only through a declared
interface — a port, a file format, a function signature. Three questions decide
whether something qualifies:

1. Can it be started, stopped, rebuilt or versioned without rebuilding its
   neighbours?
2. Do its neighbours reach it only through that declared interface, never
   through its internals?
3. Can it fail without taking the rest down, observably from outside?

| Component | Path | Interface | Responsibility |
| --- | --- | --- | --- |
| **api** | `runtime/api/` | `:8000` HTTP + SSE | Debate orchestration, citation resolution, run persistence |
| **frontend** | `runtime/frontend/` | `:3000` dev, `:80` prod | Courtroom view, dissent log, citation inspection |
| **qdrant** | *(image)* | `:6333` | Holds the `ihl_corpus` collection |
| **ollama** | *(image)* | `:11434` | Serves both attacker models locally |
| **fetcher** | `pipeline/fetcher/` | reads manifests → `data/cache/` | Downloads the manifest-defined corpus |
| **indexer** | `pipeline/indexer/` | `data/cache/` → Qdrant + index | Chunks, embeds, writes the citation index |

### What is deliberately *not* a component

This matters more than the list above, because the exclusions are where the
word usually gets stretched.

- **The four roles** — presenter, two attackers, judge — are Python modules
  inside the `api` container, sharing its process and lifecycle. They look like
  independent agents and are often drawn as four boxes, but the debate is
  sequential: only the attacker pair ever overlaps, and that pair shares memory
  rather than a network. Four containers would buy serialisation and network
  hops and nothing else — [ADR 0003](adr/0003-single-orchestrator-service.md).
- **`council-core`** is a library, compiled into whatever imports it. It ships
  as the `council-base` image that `api`, `fetcher` and `indexer` all build
  `FROM`, which is the only form in which it is deployed.
- **`evaluation`** is a harness run by hand, not a service. It has no image, no
  port and no uptime.

The dependency arrow points one way: services import from `council-core`;
`council-core` imports from nothing in the repo. That keeps the domain model
testable without standing up Qdrant or calling a model.

### Two regions, one interface

The components divide into an **offline pipeline** (`fetcher`, `indexer`) and an
**online runtime** (`api`, `frontend`, `qdrant`, `ollama`). They have separate
compose files and never run at the same time.

The only channel between them is the two datastores: the pipeline writes the
Qdrant collection and the citation index, the runtime reads them. There is no
network path, no shared process, no API call. That is what makes a corpus
rebuild safe to run while the service is up, and what lets the runtime be tested
against a frozen corpus snapshot.

---

## The debate graph

Built with LangGraph in `runtime/api/app/graph/workflow.py`. The compiled graph
is a **module-level singleton created at import**, so adding or renaming a node
means editing `build_graph()` and restarting the server.

### Nodes

| Node | File | What it does |
| --- | --- | --- |
| `retrieve` | `nodes/retrieve.py` | Embeds the question, pulls top-k corpus spans. Skipped when `retrieval_enabled=False` (ablation arm A) |
| `present` | `nodes/present.py` | Presenter argues. Round 1 opens; later rounds rebut |
| `attacker_doctrinal` | `nodes/attack.py` | Challenges legal characterisation |
| `attacker_evidentiary` | `nodes/attack.py` | Challenges factual predicate |
| `judge` | `nodes/judge.py` | Rules on every objection, produces the verdict |

### Parallelism, and the trap in it

The two attackers **fan out** from `present` and **fan in** to `judge`. They read
the same arguments and write disjoint objections, so serialising them would only
cost wall-clock time.

The trap — and this has bitten a prior project in this codebase family:

> **A parallel node must return ONLY the keys it writes.**
>
> Returning `{**state, ...}` from either attacker raises
> `InvalidUpdateError: At key 'config': Can receive only one value per step`,
> because two concurrent writers to a single-value channel is an error even when
> the values are identical.

`turns`, `arguments`, and `objections` use `operator.add` reducers so concurrent
appends merge. Everything else uses the default last-write-wins channel, which
is why only one node may write to it per step.

### Round control

`should_continue` in `workflow.py` decides after each ruling:

- **Fixed mode** (`rounds: 2`) — continue until the count is reached
- **Auto mode** (`rounds: "auto"`) — the judge sets `novel_objections_raised`;
  when false, the debate terminates as `no_novel_objections`
- **Always** bounded by `config.max_rounds` (default 3, hard max 5)

The ceiling is absolute. A debate that cannot terminate would drain a free-tier
quota in minutes, so `test_workflow.py` covers termination directly.

---

## Roles

Each role owns its prompt ids, its response schema, and its parsing.
`BaseRole` (`app/roles/base.py`) holds what they share.

**Citation resolution happens at the role boundary.** `ground_arguments` and
`ground_objections` run before a turn is recorded, so an argument reaches the
judge already marked grounded or unsupported and no downstream code has to
remember to check.

Attackers overwrite the `raised_by` field on every objection with the true role
after parsing, so a model cannot attribute its objections to its counterpart —
which would corrupt the independence metric.

---

## Retrieval

Embeddings run through **fastembed** (ONNX), not PyTorch — see
[ADR 0001](adr/0001-no-torch-fastembed.md). Qdrant holds the corpus.

`RetrievalService.encode` runs in a thread executor. fastembed is synchronous
and would otherwise block the event loop while four model calls are in flight.

Retrieved spans come back as `ResolvedCitation`, the same type model-emitted
citations resolve to. That means retrieved context and cited authority share one
type from Qdrant through to the React component.

> **The embedding model must match between indexer and API.** A collection built
> with one model and queried with another returns meaningless scores, silently.
> `EMBEDDING_MODEL` is set once and read by both.

---

## Citation integrity

The anti-fabrication machinery, and the project's central technical claim.
Detailed in [ADR 0004](adr/0004-citation-integrity.md).

```
model emits structured Citation
        ↓
CitationResolver.resolve()
        ↓
lookup locator in citation_index.json
        ↓
┌────────────┬──────────────┬────────────────┬────────────┐
│ resolved   │ unresolved   │ out_of_corpus  │ misquoted  │
│ text found │ FABRICATION  │ unverifiable   │ text wrong │
└────────────┴──────────────┴────────────────┴────────────┘
        ↓
shown to the judge, displayed in the UI, counted in metrics
```

`unresolved` and `out_of_corpus` must stay distinct. Merging them would penalise
a model for citing real authority the corpus does not index, and the fabrication
rate would stop meaning anything.

---

## SSE streaming

`POST /debate/stream` streams **turn-level** events, not tokens. A four-model
debate runs for minutes; what a viewer wants is "the doctrinal attacker raised
three objections", not characters trickling out of a 12B model.

| Event | Payload |
| --- | --- |
| `start` | `{run_id}` |
| `turn` | The full `Turn` object |
| `verdict` | The `Verdict` |
| `error` | `{error}` |
| `done` | `{run_id, status}` |

The endpoint is a POST, so the frontend cannot use `EventSource` (GET only). It
reads the response body as a stream and parses SSE frames by hand — which also
makes aborting a run clean.

Concurrency is bounded by a semaphore. Three of four roles run on free-tier
quotas; unbounded concurrency exhausts them and every in-flight run fails
together.

---

## Persistence

One directory per run under `data/runs/<run_id>/`: `artifact.json` plus rendered
`dissent.md` and `dissent.html`. Flat files, not a database — see
[ADR 0005](adr/0005-json-run-artifacts.md).

The artifact records model ids **as resolved**, temperatures, seed, prompt
template hashes, and corpus version. If a prompt changes, its hash changes, and
a stored result can never be silently attributed to a prompt that has since been
edited.

---

## Frontend

Two visual registers, deliberately:

- **Courtroom** — the live proceeding. Four benches, bobbing sprites, speech
  bubbles as turns land, an OBJECTION! slam when an attacker files one.
- **Dissent log** — the record. Parchment, serif, numbered entries, citation
  chips showing resolution status. This is the half you hand to someone.

Zustand holds both the debate record and the presentational state in one store,
so a single SSE event updates both atomically and the sprites can never disagree
with the transcript.

Animations respect `prefers-reduced-motion` — the courtroom is decorative and
carries no information the transcript does not.

---

## Configuration

| Variable | Read by | Purpose |
| --- | --- | --- |
| `COUNCIL_*_MODEL` | api | LiteLLM model id per role |
| `COUNCIL_OLLAMA_BASE_URL` | api | Host or containerised Ollama |
| `EMBEDDING_MODEL` | api, indexer | **Must match between them** |
| `QDRANT_URL` | api, indexer | Service name in compose, localhost in pipeline |
| `MAX_CONCURRENT_DEBATES` | api | Free-tier quota guard |

Prod and dev differ only through compose overrides — `docker-compose.override.yml`
loads automatically for dev; `docker-compose.prod.yml` is explicit.
