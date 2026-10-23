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

Be clear about this before you start: **the debate has never run end to end
against live models.** The corpus it would argue over does exist.

| Area | State |
| --- | --- |
| Domain models, LLM gateway, citation resolver | Written, tested |
| Debate graph, roles, SSE, run persistence | Written, tested — **never completed a live run** |
| Frontend | Written in full — **never run against a real stream** |
| Corpus fetcher and parsers | **Working** — 23 instruments plus the 161 customary rules |
| Citation index | **Working** — all four statuses resolve against real text |
| Qdrant embedding and upsert | Written; the first full index run is slow and memory-hungry |
| Evaluation metrics | Written — **zero tests** |
| Evaluation harness runner | **Does not exist** |

Consequences you will hit immediately:

- **The judge has never returned a verdict.** `gemini-2.5-pro` was retired
  mid-project; see ISSUES.md for what to set instead.
- `data/runs/` is empty, so there is no example artifact to look at.
- `make eval` cannot run — there is no runner.

**Two things worth reading before you start**, both of which will save you a
day. [ISSUES.md](../../ISSUES.md) lists what is broken and what was found
running the system for the first time. [corpus-findings.md](../corpus-findings.md)
collects the eleven problems that came up building the corpus — eight of which
produced plausible wrong output rather than an error, which is the failure
mode this project can least afford.

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
| `GROQ_API_KEY` | console.groq.com | presenter |
| `GEMINI_API_KEY` | aistudio.google.com | judge |

Pull the attacker models:

```bash
ollama pull qwen3.5:14b     # doctrinal attacker
ollama pull gemma3:12b      # evidentiary attacker
```

Then, in every shell you work in:

```bash
source scripts/dev-env.sh
```

That sets the data paths and points Ollama at localhost. Scripts run outside
Docker also need `--env-file .env` to see your API keys:
`uv run --env-file .env python scripts/...`.

> **Cannot run the attackers locally?** Two documented alternatives, both
> config-only (ADR 0002, ADR 0006): `make up-ollama` for a containerised Ollama
> with a shared model store, or point the attackers at Cloudflare Workers AI
> (~10,000 neurons/day free, roughly 30 single-case runs). Either way, **record
> which models you ran** — it changes what the results mean.

> **The canonical setup steps, in order, are the quickstart in
> [README.md](../../README.md#quick-start).** This section explains what each
> one does; the README is what to follow.

### Getting the corpus

```bash
make fetch          # 24 documents: 23 treaties + the 161 customary rules
make index-local    # embed and upsert, under a memory cap
```

`make fetch` takes seconds. **`make index-local` does not** — it embeds ~2,200
spans with a 1.2GB model, and on a 16GB laptop that is enough to get something
OOM-killed. It runs inside a systemd scope with a hard memory ceiling so the
job dies rather than your editor; raise it with `MEM_CAP=6G` if the job is
what gets killed. Safe to interrupt: point ids come from locators, so
re-running overwrites rather than duplicating.

> **Working without Qdrant?** `RETRIEVAL_BACKEND=stub` serves word-overlap
> matches from the citation index instead. It is not semantic search and must
> never be used for a scored run — it logs a warning on every call so a stray
> one is visible in the output.

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
make check     # lint + the full suite — proves the code is sound
make doctor    # proves YOUR machine is set up
```

`make doctor` is read-only and changes nothing. It reports what is installed,
whether `.env` has keys, whether the citation index is in place, whether Qdrant
is up and how many points it holds — then prints what to run next. Run it
whenever something behaves oddly; it is faster than guessing.

### Resetting things

| Command | Removes | Keeps |
| --- | --- | --- |
| `make clean` | caches, build artifacts | everything in `data/` |
| `make reset-qdrant` | the Qdrant volume | pulled Ollama models |
| `make reindex` | the Qdrant collection, then rebuilds | `data/cache/`, so no re-fetch |
| `make clean-runs` | saved debate runs | everything else |
| `make nuke` | **all** volumes — full clean slate | nothing |

All of these prompt before destroying anything. `make nuke` is the start-over
button; `make reset-qdrant` is there for when only the index is wrong and
re-pulling ~17GB of models would be beside the point.

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
| What went wrong building it? | [corpus-findings.md](../corpus-findings.md) |
| How do I write a fixture? | [fixtures-guide.md](fixtures-guide.md) |
| What am I doing this week? | [implementation-plan.md](implementation-plan.md) · [timeline.md](timeline.md) |
| How do I get the first debate running? | [t0-runbook.md](t0-runbook.md) |
