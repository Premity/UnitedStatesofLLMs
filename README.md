# United States of LLMs

**A council of AI models that argue international law with each other — and shows you what it argued about.**

> Research prototype for the Skill Lab (Generative AI) module. Not legal advice.
> See [DISCLAIMER.md](DISCLAIMER.md).

---

## The problem

Ask a large language model whether a particular military strike was a war crime
and you will get an answer. It will be fluent, well-organised, and confident.

It will also, quite often, be wrong in a way that is hard to see. A single-pass
model smooths over the weak points in its own reasoning rather than exposing
them. It will not tell you that opposing counsel has a strong response to its
central argument, because nothing asked it to look. And it has a documented
habit of citing cases that do not exist — with paragraph numbers, in the correct
format, entirely invented.

In international humanitarian law this matters more than usual. Whether conduct
satisfies proportionality, or distinction, or command responsibility, is exactly
the kind of question that real tribunals decide *narrowly*, over the objections
of serious lawyers arguing the other way. A tool that flattens that contest into
one confident paragraph is not just incomplete — it is misleading about how
settled the question is.

## The approach

Replace the single pass with an argument.

Four models take four roles, drawn deliberately from **different model
families** so the disagreement between them is genuine rather than one base
model play-acting a dispute with itself:

| Role | What it does | Model | Where it runs |
| --- | --- | --- | --- |
| **Presenter** | Argues the position | Mistral Magistral | Mistral API (free tier) |
| **Doctrinal attacker** | Challenges the *legal characterisation* | Qwen3.5 | Local, Ollama |
| **Evidentiary attacker** | Challenges the *factual predicate* | Gemma 3 12B | Local, Ollama |
| **Judge** | Rules on every objection, calibrates confidence | Gemini 2.5 Pro | Google AI Studio (free tier) |

Capability is allocated by difficulty. Building a defensible legal argument is
harder than attacking one, and the presenter sets the quality ceiling for the
whole debate — an attacker can only test the case it is given. The judge has to
tell a sound objection from a merely plausible one. Those two roles get frontier
models; the attackers run locally and unmetered.

The two attackers are separated by **mandate**, not capability. One challenges
whether the law was applied correctly; the other challenges whether the facts
support what the argument needs them to. That split mirrors how argument is
actually allocated in adversarial proceedings — and it gives us a measurable
quantity: how much the two attackers overlap. If they raise the same objections,
the second one is not earning its place, and we would rather find that out and
report it than assume otherwise.

Every role is tethered to authoritative sources — the Geneva Conventions and
their Additional Protocols, the Rome Statute, customary IHL, and the
jurisprudence of the ICC, ICJ, and the ad hoc tribunals — through retrieval over
an indexed corpus.

## The output that matters

Not the conclusion. **The dissent log.**

When the judge rules, it records every objection it *overruled* and why. That
record is the deliverable: a source-anchored trail showing which counterarguments
the conclusion had to survive, and where it remains genuinely contested.

A conclusion with a 62% confidence and four overruled objections tells you
something a confident paragraph never will.

### Citations are checked, not trusted

Every citation a model emits is structured — instrument, article, paragraph —
and every one is resolved against the corpus index before it reaches the judge.
A citation that does not resolve is **flagged in the output**, not quietly
accepted:

- `resolved` — the locator exists and the text was retrieved
- `unresolved` — the instrument is indexed, but nothing is at that locator (**the fabrication signal**)
- `out_of_corpus` — real authority we have not indexed; unverifiable here, reported separately
- `misquoted` — the locator resolves, but the quoted words are not in it

This is machinery, not a prompt instruction. A model cannot talk its way past
it, because the check never reads the model's prose.

---

## Does it actually work?

That is an empirical question, and the repo is set up to answer it honestly
rather than to flatter the design. Four arms, each differing from the last in
exactly one respect:

| Arm | Configuration | Isolates |
| --- | --- | --- |
| **A** | Single pass, no retrieval | The raw baseline |
| **B** | Single pass + retrieval | What grounding alone contributes |
| **C** | Presenter + 1 attacker + judge | What adversarial challenge contributes |
| **D** | Full council (2 attackers) | Whether the second attacker earns its place |

Scored against adjudicated cases where a tribunal's holding is the ground truth:

- **Outcome agreement** — did it reach the conclusion the tribunal reached?
- **Calibration** (Brier score, ECE) — is it *appropriately uncertain*? This is
  where the council should beat a single pass most visibly: single-pass models
  are confidently wrong, and a council that says 60% on a genuinely contested
  question is doing better than one that says 95%.
- **Citation validity** — what fraction of citations resolve? Fully automatic.
- **Attacker independence** — do the two attackers actually raise different objections?

With 40–80 cases the confidence intervals are wide, so the harness reports
bootstrap intervals and we do not oversell small gaps.

---

## Quick start

**Prerequisites:** Docker + Compose v2, [uv](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com/download) (or use the containerised profile).

```bash
git clone <repo-url> && cd UnitedStatesofLLMs

make setup            # env file, Python deps, git hooks
# fill in MISTRAL_API_KEY and GEMINI_API_KEY in .env

ollama pull qwen3.5:14b
ollama pull gemma3:12b

make up               # start the stack
make corpus           # fetch and index the corpus (first run only)
```

Then open **http://localhost:3000**.

Run `make help` for everything else.

> **Note:** the corpus fetcher and indexer are scaffolded but not yet
> implemented — see [ISSUES.md](ISSUES.md). Until they are, retrieval returns
> nothing and every citation resolves as `out_of_corpus`.

---

## The interface

Two registers, side by side.

The **courtroom** is the live view: four benches, sprites that bob while their
model is thinking, speech bubbles as turns land, and an OBJECTION! slam when an
attacker files one. A four-model debate takes minutes, and watching it unfold
beats a spinner.

The **dissent log** is the record: parchment, serif, numbered entries, citations
with their resolution status visible. Downloadable as Markdown or print-ready
HTML. That is the half you hand to someone else.

Whimsy in the presentation, sobriety in the record.

---

## How it is put together

```
                        ┌─ attacker: doctrinal ──┐
retrieve → present ─────┤                        ├──→ judge ──→ dissent log
     ↑                  └─ attacker: evidentiary ┘        │
     └──────────────── next round (if any) ───────────────┘
```

Orchestrated with LangGraph. The two attackers run **in parallel** — they read
the same arguments and write disjoint objections, so there is no reason to
serialise them. Rounds are user-configurable, or `auto`, where the judge stops
the debate once the attackers stop raising anything new. Always bounded.

```
├── corpus/            Tier 1 treaty text (committed) + the manifests defining scope
├── data/              Fetched jurisprudence, embeddings, run artifacts (gitignored)
├── packages/
│   └── council-core/  Shared domain models, LLM client, citation validator, exports
├── pipeline/
│   ├── fetcher/       Downloads exactly what the manifests list — never crawls
│   └── indexer/       Chunks at citation granularity, embeds, indexes
├── runtime/
│   ├── api/           LangGraph orchestrator, SSE streaming, run artifacts
│   └── frontend/      React courtroom + dissent log
├── evaluation/        Ablation harness, metrics, case fixtures
├── prompts/           Versioned prompt templates, hashed into every run
└── docs/              Architecture, corpus, evaluation, API contract, ADRs
```

**No PyTorch anywhere.** Embeddings run through fastembed's ONNX runtime —
66MB against PyTorch+CUDA's ~2.5GB — so there is no shared-base-image dance, no
CUDA wheel variants, and nobody downloads CUDA fifteen times.
([ADR 0001](docs/adr/0001-no-torch-fastembed.md))

**Every model behind one gateway.** LiteLLM means switching the attackers from
local Ollama to Cloudflare Workers AI for a hosted demo is an env-var change,
not a code change. ([ADR 0002](docs/adr/0002-litellm-model-gateway.md))

---

## Documentation

| Document | What it covers |
| --- | --- |
| [docs/system-design.md](docs/system-design.md) | **Full system design** — requirements, components, data flow, failure modes |
| [docs/architecture.md](docs/architecture.md) | Narrative walkthrough of the debate graph |
| [docs/development.md](docs/development.md) | Every command, the dev loop, troubleshooting |
| [docs/corpus.md](docs/corpus.md) | Corpus tiering, document shapes, chunking rules |
| [docs/evaluation.md](docs/evaluation.md) | Ablation design, metrics, how to write a case |
| [docs/data-model.md](docs/data-model.md) | Every domain type and how they relate |
| [docs/api-contract.md](docs/api-contract.md) | Endpoints, SSE event shapes |
| [docs/adr/](docs/adr/) | Why the significant decisions went the way they did |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branching, commit format, PR process |
| [ISSUES.md](ISSUES.md) | What is not built yet |

---

## The team

Skill Lab — Generative AI · *Council of AI*

| Name | USN |
| --- | --- |
| Adya Avinash | 1MS23CI006 |
| Anudveg Tummala | 1MS23CI015 |
| Diya Vipin | 1MS23CI034 |
| Mohammad Hamd Ashfaque | 1MS23CI068 |

## License

[MIT](LICENSE)
