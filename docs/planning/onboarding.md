# Onboarding

Read this first. It tells you what this project is, what actually works today,
how to get it running, and how to pick up work.

Written for someone joining with no prior context. Fifteen minutes.

---

## 1. What this is

Four language models argue a question of international humanitarian law. A
**presenter** builds a legal position; two **attackers** with deliberately
separate mandates try to break it; a **judge** rules on every objection and
states a calibrated confidence.

**The output is not the answer.** It is the **dissent log** — the record of
which objections were raised, which the judge overruled, and why. A conclusion
carrying 62% confidence and four recorded overruled objections tells you where
the answer is contested and what it had to survive. A fluent paragraph does not.

This is an academic project. It is not legal advice and is not usable as a legal
research tool — see [DISCLAIMER.md](../../DISCLAIMER.md).

### Why it is built this way

The literature review found three gaps this design answers:

| Gap | Response |
| --- | --- |
| Citations are checked only *after* an answer is written | Every citation is resolved against an indexed corpus **at the role boundary**, before the judge reads it |
| Adversarial scrutiny is simulated — all agents are one model | The four roles run on **four different model families**, so disagreement is a property of the models, not the sampling temperature |
| Reported confidence does not track correctness | The judge must justify a calibrated confidence, and we measure its calibration explicitly |

If you read nothing else, read [docs/architecture.md](../architecture.md).

---

## 2. What actually works today

Be clear about this before you start: **the system has never run end to end.**

| Area | State |
| --- | --- |
| Domain models, LLM gateway, citation resolver | Written, tested (9 tests) |
| Debate graph, roles, SSE, run persistence | Written, tested (12 tests) — **never run against live models** |
| Frontend | Written in full — **never run against a real stream** |
| Evaluation metrics | Written — **zero tests** |
| Evaluation harness runner | **Does not exist** |
| Corpus fetcher | **Stub** — 70 lines, no source parsers |
| Corpus indexer | **Stub** — 65 lines, no chunking or embedding |

Consequences you will hit immediately:

- Retrieval returns nothing, so **every citation resolves as `out_of_corpus`**.
- `data/runs/` is empty. There is no example artifact to look at yet.
- `make eval` cannot run — there is no runner.

This is the work. See [implementation-plan.md](implementation-plan.md).

---

## 3. Getting it running

### Prerequisites

- Docker Engine with Compose v2
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- ~16 GB RAM (a quantised 12–14B attacker model needs 8–10 GB resident)
- [Ollama](https://ollama.com) on the host, for the two attacker models

### First time

```bash
make setup          # .env from template, Python deps, git hooks
```

Then edit `.env` and add two keys — both have free tiers:

| Variable | Where from | Used by |
| --- | --- | --- |
| `MISTRAL_API_KEY` | console.mistral.ai | presenter |
| `GEMINI_API_KEY` | aistudio.google.com | judge |

Pull the attacker models:

```bash
ollama pull qwen3.5:14b     # doctrinal attacker
ollama pull gemma3:12b      # evidentiary attacker
```

> **No GPU?** The attackers still run on CPU, just slowly. Alternatively use the
> containerised Ollama profile — see [docs/development.md](../development.md).

### Running

```bash
make up             # dev stack: API :8000, frontend :3000, Qdrant :6333
make check          # lint + tests — this is what CI runs
make test           # tests only, fast, no network
```

`make up` builds the shared base image first. A bare `docker compose build`
does not, and you will get `council-base: image not found`.

### Verify your setup

```bash
make check
```

23 tests should pass. If they do, your environment is correct — even though the
system itself is incomplete.

---

## 4. How the code is laid out

```
packages/council-core/   Domain models, LLM gateway, citation resolver, exports
runtime/api/             Debate graph, roles, SSE, run persistence
runtime/frontend/        Courtroom view, dissent log
pipeline/fetcher/        Corpus download          (STUB)
pipeline/indexer/        Chunk, embed, index      (STUB)
evaluation/              Ablation arms, metrics, case fixtures
prompts/                 Versioned templates, hashed into every run
corpus/manifests/        Defines corpus scope — the fetcher never crawls
docs/adr/                Why decisions went the way they did
```

**The dependency arrow points one way.** Services import `council-core`;
`council-core` imports nothing from the repo. That is what lets the domain model
be tested without Qdrant or a model call.

### The debate graph

```
retrieve → present → [attacker_doctrinal ∥ attacker_evidentiary] → judge → (loop or END)
```

Built with LangGraph in `runtime/api/app/graph/workflow.py`, compiled as a
module-level singleton **at import**. Adding or renaming a node means editing
`build_graph()` and restarting.

---

## 5. Things that will silently break

These fail without raising. Each one produces plausible-looking but wrong
results, which is worse than a crash. The full register is in
[system-design.md §11.2](../system-design.md).

1. **A parallel node must return only the keys it writes.** Both attackers run
   concurrently. `return {**state, ...}` raises `InvalidUpdateError` — two
   writers to a single-value channel is an error even when the values match.

2. **`unresolved` ≠ `out_of_corpus`.** `unresolved` means the model invented an
   authority. `out_of_corpus` means it cited something real that we chose not to
   index. Merging them makes the fabrication metric meaningless.

3. **`EMBEDDING_MODEL` must match between indexer and API.** A mismatch gives
   meaningless similarity scores and no error.

4. **Chunk at citation granularity** — treaty article, judgment paragraph. Token
   windows would make `icty_galic_tj/para.58` unresolvable.

5. **Prompts live in `prompts/`, never inlined.** Their hashes go into every run
   artifact; an inlined prompt cannot be tracked.

6. **Debates must terminate.** `max_rounds` is a hard ceiling in every mode. An
   unbounded loop drains the judge's daily quota in minutes.

---

## 6. How we work

**Branches:** `main` ← `develop` ← `feature/*`. The pre-commit hook blocks
direct commits to `main` and `develop`. Merge with `make merge-develop`.

**Commits:** Conventional Commits, enforced by hook and CI.

```
feat(api): stream turn-level events over SSE
```

Scopes: `api` `core` `frontend` `fetcher` `indexer` `eval` `prompts` `corpus`
`docker` `ci` `docs` `deps`

**Before pushing:** `make check` must pass. It is what CI runs.

**Decisions with trade-offs get an ADR** in [docs/adr/](../adr/). If you make a
choice that someone could reasonably have made differently, write it down.

---

## 7. Picking up work

1. Read [implementation-plan.md](implementation-plan.md) — work is organised
   into five **tracks**.
2. Claim a task in standup. Tasks are sized at roughly half a day to two days.
3. Check the task's **Depends on** before starting. If it is unmet, pick another.
4. Check the **Touches** column. If someone else is in those files, coordinate.
5. A task is done when its **Done when** command passes. Not before.

**Everyone also writes case fixtures.** It is the one task that cannot be
hurried at the end, and the one where four people genuinely beat one person
working four times as long. See [fixtures-guide.md](fixtures-guide.md).

### Where to look

| Question | File |
| --- | --- |
| How does the system work? | [architecture.md](../architecture.md) |
| What are the formal contracts? | [system-design.md](../system-design.md) |
| Why was X decided? | [adr/](../adr/) |
| What is broken or missing? | [ISSUES.md](../../ISSUES.md) |
| How do I evaluate it? | [evaluation.md](../evaluation.md) |
| What is the corpus? | [corpus.md](../corpus.md) |
| How do I write a fixture? | [fixtures-guide.md](fixtures-guide.md) |
| What am I doing this week? | [implementation-plan.md](implementation-plan.md) · [timeline.md](timeline.md) |
