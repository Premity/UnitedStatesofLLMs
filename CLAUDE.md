# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

An adversarial multi-agent debate system for international humanitarian law
analysis. Four models — presenter, two attackers separated by mandate, judge —
argue a legal question; the output is a **dissent log** recording which
objections the judge overruled and why.

Academic project. Not legal advice — see [DISCLAIMER.md](DISCLAIMER.md).

## Commands

```bash
make help          # every target
make setup         # first-time: env, deps, hooks
make up            # dev stack (hot reload)
make check         # lint + tests — what CI runs
make test          # tests only (fast, no network)
make fmt           # auto-fix and format
make corpus        # fetch + index (not yet implemented)
make eval          # ablation harness — SLOW, consumes API quota
```

Single test: `uv run pytest packages/council-core/tests/test_citations.py::test_flags_a_fabricated_article_in_a_known_instrument -v`

## Layout

```
packages/council-core/   Domain models, LLM gateway, citation validator, exports
runtime/api/             LangGraph orchestrator, SSE, run persistence
runtime/frontend/        React courtroom + dissent log
pipeline/fetcher/        Corpus download (SCAFFOLD ONLY)
pipeline/indexer/        Chunk, embed, index (SCAFFOLD ONLY)
evaluation/              Ablation arms, metrics, case fixtures
prompts/                 Versioned templates, hashed into every run
corpus/manifests/        Defines corpus scope — the fetcher never crawls
docs/adr/                Why decisions went the way they did
```

Dependency arrow points one way: services import `council-core`; `council-core`
imports nothing from the repo.

## Architecture essentials

**The graph** (`runtime/api/app/graph/workflow.py`), compiled as a module-level
singleton at import — adding a node means editing `build_graph()` and
restarting:

```
retrieve → present → [attacker_doctrinal ∥ attacker_evidentiary] → judge → (loop or END)
```

**Roles are modules, not services** (`app/roles/`). The debate is sequential;
four containers would buy network hops and nothing else. ADR 0003.

**Citation resolution happens at the role boundary** (`BaseRole.ground_*`), so
arguments reach the judge already marked grounded or unsupported.

## Non-negotiables

These are load-bearing. Breaking one produces silent, hard-to-diagnose failure.

1. **Parallel nodes return ONLY the keys they write.** Both attackers write
   `turns` and `objections` concurrently. `return {**state, ...}` raises
   `InvalidUpdateError`.

2. **`unresolved` ≠ `out_of_corpus`.** `unresolved` = fabrication signal;
   `out_of_corpus` = real authority we did not index. Merging them makes the
   fabrication metric meaningless. ADR 0004.

3. **`EMBEDDING_MODEL` must match between indexer and API.** A mismatch gives
   meaningless similarity scores with no error.

4. **Chunk at citation granularity** — treaty article, judgment paragraph. Token
   windows would make `icty_galic_tj/para.58` unresolvable.

5. **Citation locator formats and corpus ids are permanent.** Both are written
   into every stored run artifact.

6. **Prompts live in `prompts/`, never inlined in Python.** Their hashes go into
   run artifacts; an inlined prompt cannot be tracked.

7. **Debates must terminate.** `max_rounds` is a hard ceiling. An unbounded loop
   drains a free-tier quota in minutes. Covered by `test_workflow.py`.

8. **`make test` never touches the network.** Live tests are
   `@pytest.mark.live` and excluded from CI.

## Conventions

**Commits:** Conventional Commits, enforced by hook and CI.
`feat(api): stream turn-level events over SSE`
Scopes: `api` `core` `frontend` `fetcher` `indexer` `eval` `prompts` `corpus`
`docker` `ci` `docs` `deps`

**Branches:** `main` ← `develop` ← `feature/*`. Never commit directly to `main`
or `develop` (the pre-commit hook blocks it).

**Python:** 3.12, uv workspace, ruff for lint + format, line length 100.

**Decisions with trade-offs get an ADR** in `docs/adr/`.

## Current state

Scaffold. The domain model, orchestration, roles, prompts, API, frontend, and
metrics are written. **The corpus fetcher and indexer are stubs** — until they
are implemented, retrieval returns nothing and every citation resolves as
`out_of_corpus`. See [ISSUES.md](ISSUES.md).

## Gotchas

- **`council-base: image not found`** — run `make build-base` first. `make up`
  does it automatically; bare `docker compose build` does not.
- **Ollama unreachable from a container on Linux** — needs
  `extra_hosts: host.docker.internal:host-gateway` (already in compose) and
  Ollama listening on `0.0.0.0`.
- **`StructuredOutputError` from an attacker** — small local models produce
  imperfect JSON. `complete_structured` retries once with the validation error
  attached; persistent failures usually mean the model is too small.
- **The TS types in `runtime/frontend/src/types/index.ts` mirror the Pydantic
  models by hand.** Update both in the same PR.
