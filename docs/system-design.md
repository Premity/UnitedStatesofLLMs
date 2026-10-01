# System Design — United States of LLMs

**Project:** Council of AI — adversarial multi-agent debate for international
humanitarian law analysis
**Version:** 0.1.0 · **Status:** Scaffold; corpus pipeline unimplemented
**Audience:** Engineers building on this system, and reviewers assessing it

> This document is the system-design reference: requirements, constraints,
> component contracts, data flow, failure modes, and capacity. For the *reasoning*
> behind individual choices see [`adr/`](adr/); for narrative orientation see
> [`architecture.md`](architecture.md).

---

## 1. Problem statement

### 1.1 The failure being addressed

A single-pass large language model, asked whether given conduct violates
international humanitarian law, returns a fluent and confident answer. Three
failure modes make that answer untrustworthy in this domain:

| # | Failure | Why single-pass produces it |
| --- | --- | --- |
| **F1** | **Unexposed counterargument** | Nothing in a single pass asks the model to find the strongest response to its own reasoning, so it does not look. Weak points are smoothed over rather than surfaced. |
| **F2** | **Overconfidence** | The model reports high certainty on questions that real tribunals decide narrowly, over serious dissent. Fluency is mistaken for settledness. |
| **F3** | **Fabricated authority** | The model emits citations with correct formatting, plausible case names, and invented paragraph numbers. This is the most documented LLM failure in legal work. |

These are **structural**, not prompt-tuning problems. F1 arises because no
adversary exists. F2 arises because nothing forces the model to price its own
uncertainty. F3 arises because plausible-looking locators are what the training
distribution rewards, so instructing the model to "only cite real sources"
produces compliance with the *form* of the instruction and not its substance.

### 1.2 Design response

| Failure | Mechanism | Enforced by |
| --- | --- | --- |
| F1 | Structured adversarial debate; two attackers with disjoint mandates | Graph topology (§4) |
| F2 | Judge must justify a calibrated confidence; overruled objections published | Judge contract (§5.4), scored in §9 |
| F3 | Structured citations resolved against a corpus index; failures surfaced | Citation subsystem (§6) |

### 1.3 Primary output

The deliverable is **not the conclusion**. It is the **dissent log** — the
objections the judge overruled, each with the judge's stated reason.

A conclusion carrying 62% confidence and four recorded overruled objections
conveys information that a confident paragraph structurally cannot: *where the
answer is contested, and what it had to survive.*

---

## 2. Requirements

### 2.1 Functional

| ID | Requirement |
| --- | --- |
| FR-1 | Accept a legal question plus a factual predicate and return a reasoned conclusion |
| FR-2 | Produce ≥2 discrete, individually contestable arguments per debate |
| FR-3 | Challenge arguments on **both** doctrinal and evidentiary grounds, independently |
| FR-4 | Rule on every objection raised, with a stated reason for each |
| FR-5 | Emit a calibrated confidence in [0,1] with a written justification |
| FR-6 | Publish overruled objections as a dissent log |
| FR-7 | Resolve every emitted citation against the corpus; surface failures |
| FR-8 | Stream debate progress at turn granularity |
| FR-9 | Persist a reproducible artifact for every run, including failures |
| FR-10 | Export the dissent log in a human-reviewable format |
| FR-11 | Support ablation: retrieval on/off, 0–2 attackers, fixed or auto rounds |

### 2.2 Non-functional

| ID | Requirement | Target | Rationale |
| --- | --- | --- | --- |
| NFR-1 | **Monetary cost** | Zero | Free-tier APIs + local inference (§10.2) |
| NFR-2 | **Termination** | Hard-bounded | Unbounded loops drain a free tier in minutes |
| NFR-3 | **Reproducibility** | Full provenance per run | Evaluation is meaningless without it |
| NFR-4 | **Model independence** | Backend = config string | Brief requires switchable attacker hosting |
| NFR-5 | **Test determinism** | No network in `make test` | CI must be fast and hermetic |
| NFR-6 | **Onboarding** | `make setup` → running | Four-person team, heterogeneous machines |
| NFR-7 | **Build time** | ~1 min per service | No PyTorch (ADR 0001) |

### 2.3 Explicit non-goals

- **Not** a legal research tool, and not usable as one ([DISCLAIMER.md](../DISCLAIMER.md))
- **Not** comprehensive in corpus coverage — deliberately curated (ADR 0007)
- **Not** a fact-finding system; facts are taken as given
- **Not** multi-tenant, authenticated, or horizontally scaled

---

## 3. System context

### 3.1 Context diagram

```
                       ┌──────────────────────────────┐
     researcher  ────► │   United States of LLMs      │
                       │                              │
                       │   courtroom view (live)      │
                       │   dissent log (record)       │
                       └──────────────┬───────────────┘
                                      │
          ┌───────────────┬───────────┼───────────┬──────────────┐
          ▼               ▼           ▼           ▼              ▼
    ┌──────────┐   ┌───────────┐ ┌────────┐ ┌──────────┐  ┌───────────┐
    │ Mistral  │   │  Google   │ │ Ollama │ │  Qdrant  │  │ ICRC/ICC/ │
    │   API    │   │ AI Studio │ │ (local)│ │  (local) │  │ ICJ/ICTY  │
    │presenter │   │   judge   │ │attacker│ │ retrieval│  │  sources  │
    │free tier │   │ free tier │ │  ×2    │ │          │  │  (fetch)  │
    └──────────┘   └───────────┘ └────────┘ └──────────┘  └───────────┘
       external        external     local       local        external
                                                             (offline)
```

### 3.2 Trust boundaries

| Boundary | Crossing | Control |
| --- | --- | --- |
| Model output → system | Untrusted text | Structured parsing + schema validation + citation resolution |
| Corpus sources → index | Untrusted documents | Manifest-scoped; never crawled (ADR 0007) |
| External APIs | Credentials leave the machine | `.env` gitignored; gitleaks in hook + CI |
| Container → host Ollama | `host.docker.internal` | Explicit `extra_hosts` mapping |

**Critical:** model output is *never* trusted as authority. A citation is
believed only if its locator resolves against the index (§6).

---

## 4. Architecture

### 4.1 Component decomposition

```
┌─────────────────────────────────────────────────────────────────┐
│ RUNTIME (online)                                                │
│                                                                 │
│  ┌───────────────┐         ┌──────────────────────────────┐    │
│  │   frontend    │◄───SSE──│           api                │    │
│  │ React 18 + TS │  POST   │  FastAPI + LangGraph         │    │
│  │ Vite/Tailwind │────────►│                              │    │
│  │ nginx (prod)  │         │  graph/ · roles/ · services/ │    │
│  └───────────────┘         └───────┬──────────────┬───────┘    │
│                                    │              │            │
│                              ┌─────▼─────┐  ┌─────▼──────┐     │
│                              │  Qdrant   │  │ data/runs/ │     │
│                              │  vectors  │  │ JSON files │     │
│                              └───────────┘  └────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ writes collection + citation index
┌───────────────────────────────────┴─────────────────────────────┐
│ PIPELINE (offline, run-to-completion)        [SCAFFOLD ONLY]    │
│   fetcher ──► data/cache/ ──► indexer ──► Qdrant + index.json   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SHARED LIBRARY — packages/council-core                          │
│   models/ · citations/ · llm/ · prompts/ · export/ · telemetry/ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ EVALUATION (offline)   arms · metrics · case fixtures           │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Module responsibilities

| Module | Path | Owns | Must not |
| --- | --- | --- | --- |
| `council-core` | `packages/council-core/` | Domain types, LLM gateway, citation validation, prompt loading, export renderers | Import from any service |
| `api` | `runtime/api/` | Debate orchestration, SSE, run persistence, retrieval | Hold business rules belonging in core |
| `frontend` | `runtime/frontend/` | Courtroom view, dissent log, citation inspection | Recompute debate state |
| `fetcher` | `pipeline/fetcher/` | Manifest-scoped corpus download | Crawl beyond the manifest |
| `indexer` | `pipeline/indexer/` | Chunking, embedding, Qdrant upsert, citation index | Chunk below citation granularity |
| `evaluation` | `evaluation/` | Ablation arms, metrics, fixtures | Run inside `make test` |

**Dependency rule:** services import `council-core`; `council-core` imports
nothing from the repo. This keeps the domain model testable without Qdrant or a
model call — the citation resolver's test suite runs against an in-memory dict.

### 4.3 Deployment topology

| Service | Image | Dev | Prod |
| --- | --- | --- | --- |
| `qdrant` | `qdrant/qdrant:v1.12.4` | ports 6333/6334 exposed | internal only, 2G cap |
| `api` | `council-api` (924 MB) | port 8000, source bind-mounted, `--reload` | baked, JSON logs, 2G cap |
| `frontend` | `council-frontend` (375 MB) | Vite HMR on 3000 | nginx, 256M cap |
| `ollama` | `ollama/ollama` | **opt-in profile** | not included |

All Python services inherit `council-base` (578 MB): pinned runtime, `uv`,
`council-core`. No PyTorch — the ONNX embedding runtime is 66 MB against
~2.5 GB for PyTorch+CUDA (ADR 0001).

Three compose files: base, `override` (auto-loaded → dev), `prod` (explicit).

> **Sizing note.** 924 MB is dominated by LiteLLM (110 MB) and its transitive
> provider SDKs (botocore, openai, grpc), not by the embedding stack. Avoiding
> torch kept ~2.4 GB out; it did not produce a small image.

---

## 5. The debate subsystem

### 5.1 Graph topology

```
                    ┌──────────────────────────┐
  START ──► retrieve ──► present ──┬──► attacker_doctrinal ───┬──► judge
                          ▲        └──► attacker_evidentiary ─┘     │
                          │                                          │
                          └────────── continue ◄─────────────────────┤
                                                                     ▼
                                                                    END
```

Compiled as a **module-level singleton at import**
(`runtime/api/app/graph/workflow.py`). Adding or renaming a node requires
editing `build_graph()` and restarting the process.

### 5.2 State channels

`GraphState` is a `TypedDict` with per-channel reducers:

| Channel | Type | Reducer | Writers |
| --- | --- | --- | --- |
| `run_id` | `str` | last-write | initial |
| `config` | `DebateConfig` | last-write | initial |
| `context` | `list[ResolvedCitation]` | last-write | `retrieve` |
| `current_round` | `int` | last-write | `present` |
| `turns` | `list[Turn]` | **`operator.add`** | all nodes |
| `arguments` | `list[Argument]` | **`operator.add`** | `present` |
| `objections` | `list[Objection]` | **`operator.add`** | both attackers |
| `verdict` | `Verdict \| None` | last-write | `judge` |
| `terminated_reason` | `str \| None` | last-write | `judge` |

> ### ⚠ Concurrency invariant
>
> **A parallel node returns ONLY the keys it writes.**
>
> Both attackers execute concurrently. Returning `{**state, ...}` raises
> `InvalidUpdateError: At key 'config': Can receive only one value per step` —
> two concurrent writers to a single-value channel is an error *even when the
> values are identical*.
>
> The `operator.add` channels exist precisely so concurrent appends merge. Every
> other channel is single-writer by construction.

### 5.3 Round control

`should_continue(state) -> "continue" | "end"`:

| Mode | Condition | Terminates when |
| --- | --- | --- |
| Fixed (`rounds: N`) | `current_round < N` | count reached |
| Auto (`rounds: "auto"`) | judge sets `novel_objections_raised` | flag is `false` → `no_novel_objections` |
| **Any mode** | — | `current_round >= max_rounds` |

`max_rounds` defaults to 3, hard-capped at 5. **The ceiling is absolute in every
mode.** NFR-2 is covered directly by `test_workflow.py`, including a
parametrised test asserting termination within 10 iterations for every valid
configuration.

### 5.4 Role contracts

Roles are **modules**, not services (ADR 0003). `BaseRole` holds construction of
the LLM client, prompt rendering, turn bookkeeping, and citation grounding.

| Role | Mandate | Model (default) | Temp | Output schema |
| --- | --- | --- | --- | --- |
| `presenter` | Build the position; rebut in later rounds | `mistral/magistral-medium-latest` | 0.4 | `{arguments: Argument[]}` |
| `attacker_doctrinal` | Legal characterisation: tests, elements, interpretation | `ollama/qwen3.5:14b` | 0.7 | `{objections: Objection[]}` |
| `attacker_evidentiary` | Factual predicate: sufficiency, mens rea, attribution | `ollama/gemma3:12b` | 0.7 | `{objections: Objection[]}` |
| `judge` | Rule on every objection; calibrate confidence | `gemini/gemini-2.5-pro` | 0.2 | `{conclusion, reasoning, confidence, rulings[], …}` |

**Capability allocation is deliberate.** Constructing a defensible argument is
harder than attacking one, and the presenter sets the quality ceiling for the
entire debate — an attacker can only test the case it is given. The judge must
distinguish a sound objection from a merely plausible one. Those two roles run
on frontier models; the attackers run locally and unmetered.

**Mandate separation is enforced in three places:** the system prompts state
what each attacker must *leave to its counterpart*; `AttackerRole` is one class
differing only by template and model, so disabling one changes nothing about the
other; and `raised_by` is overwritten with the true role after parsing, so a
model cannot attribute objections to its counterpart and corrupt the
independence metric (§9.4).

### 5.5 Turn lifecycle

```
render prompt (+ hash)  →  start_turn()  →  LLM call
        │                                       │
        │                                   parse to schema
        │                                       │ fail
        │                                   repair retry (once)
        │                                       │
        ▼                                  ground citations
  prompt_hash                                   │
  recorded                               finish_turn(tokens, timing)
                                                │
                                        append to state.turns
```

Citation grounding happens **at the role boundary**, so arguments reach the
judge already marked grounded or unsupported and no downstream code must
remember to check.

---

## 6. Citation integrity subsystem

The anti-fabrication machinery, and the project's central technical claim
(ADR 0004).

### 6.1 Why machinery and not a prompt

A prompt saying "only cite real sources" fails because the check would still be
performed by the same model that produced the citation. This subsystem **never
reads the model's prose** — only its structured locator — so a model cannot
argue its way past it.

### 6.2 Flow

```
model emits Citation {type, instrument, article|case_id+paragraph|rule_number}
                              │
                    locator() → "rome_statute/art.8(2)(b)(iv)"
                              │
                 ┌────────────┴────────────┐
                 │  completeness check     │  missing required field → UNRESOLVED
                 └────────────┬────────────┘
                              │
                  lookup in citation_index.json
                              │
         ┌────────────────────┼────────────────────┐
     found                 not found          found, quote mismatch
         │                    │                     │
    ┌────▼────┐   instrument indexed?          ┌────▼─────┐
    │RESOLVED │      │            │            │MISQUOTED │
    └─────────┘     yes           no           └──────────┘
                     │            │
              ┌──────▼─────┐ ┌────▼──────────┐
              │UNRESOLVED  │ │OUT_OF_CORPUS  │
              │FABRICATION │ │ unverifiable  │
              └────────────┘ └───────────────┘
```

### 6.3 Status semantics

| Status | Meaning | Counts as fabrication? |
| --- | --- | --- |
| `resolved` | Locator exists; corpus text attached | — |
| `unresolved` | Instrument **is** indexed; locator absent | **Yes** |
| `out_of_corpus` | Instrument never indexed | **No** — unverifiable ≠ invented |
| `misquoted` | Locator resolves; quoted text absent from span | **Yes** |

> ### ⚠ Semantic invariant
>
> **`unresolved` and `out_of_corpus` must never be merged.**
>
> Merging them would penalise a model for citing genuine authority the curated
> corpus does not happen to index, and the fabrication rate would stop measuring
> fabrication. This distinction is load-bearing for §9.3 and is pinned by tests.

### 6.4 Design details

- **Locator formats are permanent.** They are written into every stored run
  artifact; changing one invalidates citation resolution for all history.
- **Quote matching is deliberately loose** (token overlap ≥ 0.6). Models
  normalise whitespace and elide with ellipses; the check targets text that is
  *not present at all*, not punctuation.
- **`CorpusIndex` is a `Protocol`**, so the resolver unit-tests against an
  in-memory dict with no Qdrant dependency.
- **Existence, not relevance.** A citation may resolve cleanly and still be
  applied to a proposition it does not support. Semantic verification is out of
  scope and is stated as a limitation in the disclaimer.

---

## 7. Retrieval subsystem

| Property | Value |
| --- | --- |
| Vector store | Qdrant 1.12.4, collection `ihl_corpus` |
| Embedding | BGE-M3 via **fastembed** (ONNX runtime, 66 MB) |
| Default `top_k` | 8 (range 1–50) |
| Return type | `ResolvedCitation` (status `resolved`) |

**One retrieval, shared by all roles.** `retrieve` runs once before the first
round. The presenter and its attackers therefore argue over the *same*
authority, rather than each retrieving a convenient subset — which would make
disagreement an artifact of retrieval rather than of reasoning.

`encode()` runs in a thread executor: fastembed is synchronous and would
otherwise block the event loop while four model calls are in flight.

Retrieved spans and model-emitted citations share one type end-to-end, from
Qdrant through to the React component — so the frontend needs no separate branch
for each.

> ### ⚠ Configuration invariant
>
> **`EMBEDDING_MODEL` must be identical in indexer and API.** A collection built
> with one model and queried with another returns meaningless similarity scores
> **with no error**. Both read the value from one place.

---

## 8. Data design

### 8.1 Domain model

```
RunArtifact
├── RunMetadata          provenance: resolved model ids, temps, seed,
│                        prompt hashes, corpus version, token totals
└── DebateState          ← the LangGraph state object itself
    ├── DebateConfig     question, facts, rounds, attackers, retrieval, top_k
    ├── context          ResolvedCitation[]   (retrieved spans)
    ├── turns            Turn[]               (every model invocation)
    ├── arguments        Argument[]           (presenter)
    ├── objections       Objection[]          (attackers)
    └── verdict          Verdict
        └── dissent      Objection[]          ← overruled; the deliverable
```

`DebateState` is not a post-hoc summary. It is the live graph state, and at
completion it *is* the dissent log.

### 8.2 Persistence layout

```
data/runs/<run_id>/
├── artifact.json     source of truth
├── dissent.md        rendered log
└── dissent.html      print-ready (→ PDF from browser)
```

Flat JSON, not a database (ADR 0005): the evaluation harness reads runs in bulk,
nothing queries across them at runtime, and an artifact stays diffable and
attachable to a bug report. **Runs are persisted on failure too**, so a debate
that died halfway remains inspectable.

### 8.3 Corpus tiering

| Tier | Content | Location | Committed |
| --- | --- | --- | --- |
| 1 | Treaties, customary IHL, UN resolutions | `corpus/` | **Yes** — small, canonical, worth diffing |
| 2 | Curated jurisprudence (~40–80 cases) | `data/cache/` | No |
| 3 | Everything else | Not ingested | → `out_of_corpus` |

Scope is defined by committed manifests; the fetcher never crawls (ADR 0007).

> ### ⚠ Chunking invariant
>
> **Chunk granularity is a correctness requirement, not a tuning knob.**
>
> | Source | Unit | Because |
> | --- | --- | --- |
> | Treaty | Article / subparagraph | `8(2)(b)(iv)` *is* the citation |
> | Judgment | Numbered paragraph | `para. 58` *is* the citation |
> | Customary IHL | Rule | `Rule 14` *is* the citation |
>
> Token-window chunking would make `icty_galic_tj/para.58` unresolvable and
> collapse the entire citation subsystem.

### 8.4 Citation index

`data/index/citation_index.json`, written by the indexer:

```json
{
  "version": "0.1.0",
  "instruments": ["rome_statute", "gc_iv", "icty_galic_tj"],
  "entries": {
    "rome_statute/art.8(2)(b)(iv)": { "text": "…", "source_url": "…" }
  }
}
```

Both fields are required. `entries` resolves locators; `instruments` is what
separates `unresolved` from `out_of_corpus`. Without the instruments list every
miss looks like fabrication and §9.3 measures nothing.

---

## 9. Evaluation design

### 9.1 Ablation ladder

Arms A–D form a ladder, each differing from the one above in **exactly one**
respect. Arm E sits beside D as a control, not on the ladder.

| Arm | Retrieval | Attackers | Max rounds | Isolates |
| --- | --- | --- | --- | --- |
| **A** `raw` | ✗ | 0 | 1 | Raw baseline |
| **B** `rag` | ✓ | 0 | 1 | Contribution of grounding alone |
| **C** `single_attacker` | ✓ | 1 (doctrinal) | 2 | Contribution of adversarial challenge |
| **D** `full_council` | ✓ | 2 | 3 | Whether the second attacker earns its place |
| **E** `self_consistency` | ✓ | 0, sampled *n*× | 1 | Whether D's gain is structural or merely more compute |

Arm B exists so the council is not credited for gains produced by retrieval
alone — without it, "beats a raw LLM" is an uninteresting claim.

**Arm E is the control that makes the claim falsifiable.** A debate spends
several model calls per question. The multi-agent debate literature reports
gains but has been criticised for not separating the contribution of the
adversarial structure from that of the additional computation the structure
consumes. D-vs-B inherits that weakness; D-vs-E does not. Its *n* is set so that
total model calls match arm D on the same case, and the comparison is reported
whichever way it falls.

> **Status:** `arms.py` implements A–D. Arm E requires compute-matched sampling
> and an aggregation rule over the samples; neither is written. Tracked in
> [ISSUES.md](../ISSUES.md).

### 9.2 Ground truth

Adjudicated cases where a tribunal's holding is the answer. The system sees
`question` and `facts`; it **never** sees `holding`, `outcome`, or
`key_reasoning`. A case whose judgment is in the corpus sets `source_case_id`,
which the harness excludes from retrieval so the answer cannot be read back.

`cases/dev/` is tuned against; `cases/held_out/` is scored once.

### 9.3 Metrics

| Metric | Module | Measures | Automatic |
| --- | --- | --- | --- |
| Outcome agreement | harness | Did it reach the tribunal's conclusion? | ✓ |
| **Brier score** | `calibration.py` | MSE of confidence vs outcome | ✓ |
| **ECE** | `calibration.py` | Bucketed confidence–accuracy gap | ✓ |
| **Overconfidence** | `calibration.py` | `mean_confidence − accuracy` | ✓ |
| Citation validity | `citations.py` | Share resolving cleanly | ✓ |
| **Fabrication rate** | `citations.py` | `(unresolved + misquoted) / total` | ✓ |
| Attacker independence | `independence.py` | Jaccard + target overlap | ✓ |
| Reasoning overlap | — | Did it anticipate the tribunal's grounds? | ✗ rubric/LLM-judge |

**Calibration is the sharpest claim.** The argument is not principally that the
council is right more often — it is that the council is *appropriately uncertain*
where a single pass is confidently wrong. `overconfidence` measures exactly that
(F2).

### 9.4 Attacker independence

Promised explicitly in the project brief. High Jaccard between the two
attackers' objection grounds means the mandate split is not working and the
second model is not earning its place.

**A negative result here is a legitimate finding and must be reported as one.**
It is also the most likely place for this design to be wrong, which makes
honesty here the most valuable output of the evaluation.

Target overlap alone is not damning — a weak argument invites challenge from
both angles. High Jaccard *combined with* high target overlap is the bad signal.

### 9.5 Statistical constraint

With 40–80 cases, differences between arms C and D carry **wide confidence
intervals**. `bootstrap_ci` is provided; a small gap with overlapping intervals
is not a result. Overselling one would be a poor look on a project whose premise
is that overconfidence is dangerous.

---

## 10. Cross-cutting concerns

### 10.1 Model gateway

All model access routes through **LiteLLM** (ADR 0002). A role's backend is a
config string in `<provider>/<model>` form, so switching the attackers from
local Ollama to Cloudflare Workers AI for a hosted demo is an environment
change, not a code change (NFR-4).

`CouncilLLM` adds three things over plain LiteLLM:

1. **Structured-output repair** — one retry with the validation error attached.
   Small local models routinely wrap JSON in prose or code fences; failing the
   turn over that would discard a usable objection.
2. **Token accounting** — flows into `RunMetadata` (NFR-1 auditing).
3. **Role-keyed logging** — logs name the role, not the raw model id.

Transport failures retry with exponential backoff. A model that answers *badly*
is not retried — that is the caller's judgement.

### 10.2 Cost and quota

| Role | Backend | Allowance |
| --- | --- | --- |
| Presenter | Mistral API | ~1B tokens/month |
| Judge | Google AI Studio | **100 requests/day** |
| Attackers ×2 | Local Ollama | Unmetered |
| Embeddings | Local fastembed | Unmetered |

The judge's daily cap is the binding constraint. `MAX_CONCURRENT_DEBATES`
(default 2) bounds concurrency via semaphore — unbounded concurrency exhausts
the quota and every in-flight run fails together.

**Capacity implication:** a full ablation over 60 cases exceeds 100 judge calls
and must span days, or run the judge locally for iteration and use the API model
only for the final scored run. Which was used **changes the result** and must be
recorded. Arm E does not change this materially — it aggregates several
presenter samples but judges once per case, so its judge cost is close to arm
B's.

### 10.3 Streaming

`POST /debate/stream` emits **turn-level** events, not tokens. A four-model
debate runs for minutes; the meaningful unit is "the doctrinal attacker raised
three objections", not characters from a 12B model.

| Event | Payload |
| --- | --- |
| `start` | `{run_id}` |
| `turn` | full `Turn` |
| `verdict` | `Verdict` |
| `error` | `{error}` |
| `done` | `{run_id, status}` |

Because the endpoint is a POST, `EventSource` (GET-only) cannot be used; the
client reads the response body as a stream and parses frames manually, which
also makes aborting a run clean.

### 10.4 Reproducibility

`RunMetadata` captures: **resolved** model ids (if config said `ollama/qwen3.5`
and Ollama served `qwen3.5:14b-q4`, the latter is recorded), temperatures, seed,
**prompt template hashes**, corpus version, and token totals.

Prompt hashing is why templates live in `prompts/` and never inline in Python: a
stored result can otherwise be silently attributed to a prompt that has since
been edited (NFR-3).

### 10.5 Observability

`structlog` — console rendering in dev, JSON in prod. Key events: `llm_request`,
`llm_response`, `present_complete`, `attack_complete`, `judge_complete`,
`argument_ungrounded`, `retrieval_search`, `run_saved`.

Health is split: `/health` (liveness) and `/health/ready`, which **reports**
`degraded` rather than raising when Qdrant is unreachable, so a partially
working stack is visible instead of appearing dead.

---

## 11. Failure modes

### 11.1 Runtime

| Failure | Detection | Handling |
| --- | --- | --- |
| Model returns unparseable JSON | Pydantic validation | One repair retry; then `StructuredOutputError`, run persisted as failed |
| Model backend unreachable | Connection error | Exponential backoff ×3 |
| Qdrant unreachable | Readiness probe | `degraded`; debate proceeds ungrounded |
| Citation index missing | File check at load | All citations → `out_of_corpus`, logged |
| Quota exhausted | Provider 429 | Surfaced as `error` event; run persisted |
| Debate fails to terminate | — | **Structurally impossible**: `max_rounds` ceiling |

### 11.2 Silent-failure register

These do not raise. They corrupt results quietly and are therefore listed in
`CLAUDE.md` as non-negotiables.

| # | Violation | Symptom | Guard |
| --- | --- | --- | --- |
| 1 | Parallel node returns full state | `InvalidUpdateError` | §5.2; code comments |
| 2 | `unresolved` merged with `out_of_corpus` | Fabrication metric meaningless | §6.3; tests |
| 3 | `EMBEDDING_MODEL` mismatch | Meaningless similarity, **no error** | §7; single source |
| 4 | Token-window chunking | Citations unresolvable | §8.3 |
| 5 | Citation locator / corpus id renamed | Past artifacts break | §6.4 |
| 6 | Prompt inlined in Python | Untracked provenance | §10.4 |
| 7 | Unbounded rounds | Quota drained in minutes | §5.3; tests |
| 8 | Network in `make test` | Non-hermetic CI | `@pytest.mark.live` |

---

## 12. Security and safety

### 12.1 Secrets

`.env` gitignored; `.env.example` documents every key. `gitleaks` runs in the
pre-commit hook **and** in CI with full history. The repository is public — four
API-key slots exist, and the habit of never pasting a key into a tracked file
matters more than either scanner.

### 12.2 Container posture

`api` runs as a non-root user (uid 1000). Production exposes only the frontend;
Qdrant is reachable solely on the internal network, and the corpus and index are
mounted read-only with only `data/runs/` writable.

### 12.3 Domain safety

The output *looks* authoritative by design — treaty citations, the register of a
legal memorandum, a numeric confidence. That is precisely what makes misuse
plausible, which is why [DISCLAIMER.md](../DISCLAIMER.md) is explicit that the
system is not legal advice, must not be used in proceedings, and must not be
used to assess identifiable parties.

Stated limitations: citation validation checks **existence, not relevance**; the
corpus is deliberately narrow; confidence scores are model-generated objects of
study, not warranties; facts are taken as given.

---

## 13. Build, test, and delivery

### 13.1 Toolchain

| Concern | Choice |
| --- | --- |
| Language | Python 3.12 (verified: fastembed + litellm + langgraph + qdrant-client resolve) |
| Packaging | `uv` workspace — 5 members, one lockfile, one venv |
| Lint + format | `ruff` (replaces flake8 + isort + black), line length 100 |
| Frontend | React 18 · TypeScript · Vite 6 · Tailwind · Zustand |

Ruff rule groups include **`ASYNC`** deliberately: the API runs an async
LangGraph pipeline calling four backends, and one blocking call in a coroutine
stalls every in-flight debate.

### 13.2 Test strategy

| Layer | Scope | Network |
| --- | --- | --- |
| `make test` | Citation resolution, termination, export rendering | **None** |
| `@pytest.mark.live` | Real backends | Excluded from CI |
| `make eval` | Ablation harness | Quota-consuming; never CI |

Two areas where tests are **not optional**: the citation resolver (if it accepts
a fabricated citation, the central claim is false) and debate termination (an
unbounded loop drains a free tier in minutes).

### 13.3 CI

Six jobs on push and PR to `main`/`develop`: lint, tests, frontend typecheck +
build, docker build, gitleaks, commitlint.

> The base image is built with `scripts/build-base.sh` — the same script
> developers run — rather than `docker/build-push-action`, whose `load: true`
> places the image in the buildx cache rather than the local store, so
> `FROM council-base` then attempts a Docker Hub pull and fails. CI exercising a
> different path from developers is how that class of bug survives.

### 13.4 Workflow

`main` ← `develop` ← `feature/*`. Conventional Commits enforced by hook and CI.
Merges use `make merge-develop` / `make merge-main`, which pass `--no-verify` on
the merge commit alone — two hooks necessarily fire on merges, and everything
being merged has already passed both individually.

---

## 14. Current state and roadmap

### 14.1 Implemented

Domain models · citation resolver (+ tests) · LiteLLM gateway · prompt loader ·
export renderers · all four roles · LangGraph orchestration (+ termination
tests) · SSE streaming · run persistence · retrieval service · React courtroom
and dissent log · evaluation arms and three metric modules · Docker stacks ·
CI · documentation.

### 14.2 Not implemented

| Gap | Impact | Blocks |
| --- | --- | --- |
| **Corpus fetcher** | No corpus documents | Retrieval, citations, evaluation |
| **Corpus indexer** | No Qdrant collection, no citation index | Same |
| Evaluation runner | Arms and metrics exist; no driver | Results |
| Case fixtures | 1 of a target 40–80 | Statistical validity |
| Sprite artwork | Placeholder plinths | Cosmetic only |

**Until the pipeline runs, retrieval returns nothing and every citation resolves
as `out_of_corpus`.** This is stated in the README, `ISSUES.md`, `CLAUDE.md`, and
`docs/corpus.md` rather than left to be discovered.

### 14.3 Open decisions

- **Judge model during development** — 100 req/day cannot absorb a full
  evaluation; local judge for iteration vs. spread across days
- **Reasoning-overlap scoring** — manual rubric vs. LLM-judge (introduces a model
  into the measurement of models)
- **Hosted demo target** — Cloudflare free tier supports ~30 runs/day

---

## Appendix A — Configuration reference

| Variable | Read by | Default | Notes |
| --- | --- | --- | --- |
| `COUNCIL_PRESENTER_MODEL` | api | `mistral/magistral-medium-latest` | |
| `COUNCIL_ATTACKER_DOCTRINAL_MODEL` | api | `ollama/qwen3.5:14b` | |
| `COUNCIL_ATTACKER_EVIDENTIARY_MODEL` | api | `ollama/gemma3:12b` | |
| `COUNCIL_JUDGE_MODEL` | api | `gemini/gemini-2.5-pro` | |
| `COUNCIL_OLLAMA_BASE_URL` | api | `http://host.docker.internal:11434` | Injected only for `ollama/` ids |
| `EMBEDDING_MODEL` | api, indexer | `BAAI/bge-m3` | **Must match** |
| `QDRANT_URL` | api, indexer | `http://qdrant:6333` | `localhost` in pipeline |
| `QDRANT_COLLECTION` | api, indexer | `ihl_corpus` | |
| `MAX_CONCURRENT_DEBATES` | api | `2` | Quota guard |
| `LOG_JSON` | api | `false` | `true` in prod |

## Appendix B — Document map

| Document | Covers |
| --- | --- |
| [architecture.md](architecture.md) | Narrative walkthrough |
| [data-model.md](data-model.md) | Every domain type, field by field |
| [api-contract.md](api-contract.md) | Endpoints, SSE shapes, error codes |
| [corpus.md](corpus.md) | Tiering, document shapes, chunking |
| [evaluation.md](evaluation.md) | Ablation design, metric definitions |
| [development.md](development.md) | Commands, troubleshooting, Docker hygiene |
| [adr/](adr/) | Seven decisions with trade-offs |
| [ISSUES.md](../ISSUES.md) | Gaps and watch list |
| [DISCLAIMER.md](../DISCLAIMER.md) | Scope limits and domain safety |
