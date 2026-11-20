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
| Adversarial scrutiny is simulated — all agents are one model | The four roles run on **three different model families** (two share GPT-OSS; ADR 0009), so disagreement is a property of the models, not the sampling temperature |
| Reported confidence does not track correctness | The judge must justify a calibrated confidence, and we measure its calibration explicitly |

If you read nothing else, read [docs/architecture.md](../architecture.md).

---

## 2. Where the project stands

Updated 2026-11-20. **Everything is built and has run live.** The open work is
evaluation, not code.

| Area | State |
| --- | --- |
| Domain models, LLM gateway, citation resolver | Written, tested |
| Debate graph, roles, SSE, run persistence | Written, tested, run live many times |
| Frontend: courtroom, dissent log, replay, theming, case picker | Written, tested, run against live streams |
| Corpus fetcher and indexer | Written, tested, run: 23 treaties plus the 161 customary rules, 3,482 indexed points |
| Sharing a built index between machines | `make export-index` / `make import-index` (ADR 0014) |
| Evaluation harness, metrics, report, arms A–E | Written, tested, run: the scored run (GitHub #26) is done |
| Case fixtures | Twenty, five of them fictional (ADR 0012, amended) |

What is left:

- **Reasoning overlap, scored by hand** (GitHub #27; `docs/evaluation.md`,
  section 5).
- **Running the `extended` tier** of cases, which have not been scored yet.
  Follow [runbook-evaluation.md](../runbook-evaluation.md).

Things you will hit early:

- **The free tiers set the pace.** The judge runs on OpenRouter's free tier
  (50 requests a day per account; the harness caps itself at 40) and the other
  roles on Groq's. One case through all five arms takes about 15 minutes and a
  fifth of a day's judge quota. Section 2 of the runbook has the numbers.
- **Two of the four roles share a model family.** The presenter and the
  evidentiary attacker both run GPT-OSS on Groq, a known compromise recorded in
  [ADR 0009](../adr/0009-presenter-on-groq.md). Don't claim "four different
  model families" without that caveat.
- **The evaluation settings are frozen.** Roster, prompts, embedding model and
  index are pinned in `evaluation/frozen-settings.json`; a live run on a
  machine that differs refuses to start. `make eval-settings` shows why.

**Two things worth reading before you start.** [ISSUES.md](../../ISSUES.md)
records what was found running the system, and what is still open.
[corpus-findings.md](../corpus-findings.md) collects the eleven problems that
came up building the corpus — eight of which produced plausible wrong output
rather than an error, which is the failure mode this project can least afford.

---

## 3. Getting it running

### Prerequisites

- Docker Engine with Compose v2
- Python 3.12 and [uv](https://docs.astral.sh/uv/)

### First time

```bash
make setup          # .env from template, Python deps, git hooks
```

Then edit `.env` and add two keys — both have free tiers:

| Variable | Where from | Used by |
| --- | --- | --- |
| `GROQ_API_KEY` | console.groq.com | presenter, both attackers |
| `OPENROUTER_API_KEY` | openrouter.ai | judge |

No local model to pull and no Ollama install needed for the default roster —
all four roles are hosted. (`COUNCIL_OLLAMA_BASE_URL` and the `ollama/`-prefixed
model ids still work if you point a role back at a local Ollama model; see
`RoleModels` in `packages/council-core/src/council_core/llm/config.py`.)

Then, in every shell you work in:

```bash
source scripts/dev-env.sh
```

That sets the data paths and, if you do switch a role to an `ollama/` model,
points Ollama at localhost. Scripts run outside Docker also need
`--env-file .env` to see your API keys: `uv run --env-file .env python scripts/...`.

> **Want a role running locally instead of hosted?** Config-only, no code
> change (ADR 0002, ADR 0006): set that role's `COUNCIL_*_MODEL` to an
> `ollama/`-prefixed id and either run `make up-ollama` (containerised Ollama,
> shared model store) or point at a host install. Cloudflare Workers AI is
> also documented as an option (~10,000 neurons/day free, roughly 30
> single-case runs). Either way, **record which models you ran** — it changes
> what the results mean.

> **The canonical setup steps, in order, are the quickstart in
> [README.md](../../README.md#quick-start).** This section explains what each
> one does; the README is what to follow.

### Getting the corpus

**Import the shared index** — the usual way, and the only one for evaluation.
Ask a teammate for the index kit (`ihl-index-kit-<hash>.zip`, sent privately:
it contains corpus text), unzip it, then:

```bash
make import-index FILE=path/to/ihl-index-<hash>.tar
docker compose restart api   # it loads the citation index once, at startup
make index-status            # its Fingerprint line must match the kit's
```

**Or build it yourself**, which an evaluation machine must not do (its index
would not match everyone else's):

```bash
make fetch          # 24 documents: 23 treaties + the 161 customary rules
make index-local    # embed and upsert, under a memory cap
```

`make fetch` takes seconds. **`make index-local` does not** — it embeds 3,482
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

`make up` does not rebuild the service images. After a pull that changes
dependencies, a Dockerfile, or the frontend's build config
(`tailwind.config.ts`, `package.json`), run `make build` first; only the
frontend's `src/`, `public/` and `index.html` are mounted live.

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
| `make reset-qdrant` | the Qdrant volume | everything else |
| `make reindex` | the Qdrant collection, then rebuilds | `data/cache/`, so no re-fetch |
| `make clean-runs` | saved debate runs | everything else |
| `make nuke` | **all** volumes — full clean slate | nothing |

All of these prompt before destroying anything. `make nuke` is the start-over
button; `make reset-qdrant` is there for when only the index is wrong and the
rest of the stack is fine.

---

## 4. How the code is laid out

```
packages/council-core/   Domain models, LLM gateway, citation resolver, exports
runtime/api/             Debate graph, roles, SSE, run persistence
runtime/frontend/        Courtroom view, dissent log
pipeline/fetcher/        Corpus download from the manifests
pipeline/indexer/        Chunk, embed, index; share a built index
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

**Branches:** `main` ← `develop` ← `feat/*` `fix/*` `chore/*` `docs/*`. The pre-commit hook blocks
direct commits to `main` and `develop`. PRs into `develop` are squash-merged on
GitHub; releases to `main` use `make merge-main`. See `CONTRIBUTING.md`.

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

The build plan's tracks are finished; [implementation-plan.md](implementation-plan.md)
and [timeline.md](timeline.md) are kept as the record of how the work was
planned. Open work is in the GitHub issues and in "What is left, in order" at
the top of [ISSUES.md](../../ISSUES.md).

1. Pick an open issue, or ask what is next.
2. Branch off `develop` (section 6).
3. Change the docs the change outdates in the same PR; the PR template's
   **Docs** section lists what to check.
4. A change is done when `make check` passes and the PR's own checks pass.

Writing a new evaluation case? Read the README in `evaluation/cases/` first:
leaking the holding into the facts is the mistake that is easiest to make and
hardest to see.

### Where to look

| Question | File |
| --- | --- |
| How does the system work? | [architecture.md](../architecture.md) |
| What are the formal contracts? | [system-design.md](../system-design.md) |
| Why was X decided? | [adr/](../adr/) |
| What is open, and what went wrong? | [ISSUES.md](../../ISSUES.md) |
| How do I evaluate it? | [evaluation.md](../evaluation.md) (design) · [runbook-evaluation.md](../runbook-evaluation.md) (steps) |
| What is the corpus? | [corpus.md](../corpus.md) |
| What went wrong building it? | [corpus-findings.md](../corpus-findings.md) |
| How do I write a case? | [evaluation/cases/README.md](../../evaluation/cases/README.md) · [fixtures-guide.md](fixtures-guide.md) |
| How was the build planned? | [implementation-plan.md](implementation-plan.md) · [timeline.md](timeline.md) (historical) |
| How was the first debate got running? | [t0-runbook.md](t0-runbook.md) (historical) |
