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
make corpus        # fetch + index — SLOW, network + embedding (see below)
make eval          # ablation harness — SLOW, consumes API quota
```

Single test: `uv run pytest packages/council-core/tests/test_citations.py::test_flags_a_fabricated_article_in_a_known_instrument -v`

## Layout

```
packages/council-core/   Domain models, LLM gateway, citation validator, exports
runtime/api/             LangGraph orchestrator, SSE, run persistence
runtime/frontend/        React courtroom + dissent log
pipeline/fetcher/        Corpus download from the ICRC JSON:API
pipeline/indexer/        Chunk, embed, index into Qdrant
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

## Asking before acting

Hamd decides anything that leaves this machine or that another person sees.
These are not guidelines to weigh — ask, every time, and wait.

**Do without asking:** read code, run tests and lint, `git status`/`log`/`diff`/
`show`/`fetch`, check out an existing branch, verify a claim empirically, write
scratch files outside the repo.

**Ask first, every time:**

- `git push`, or creating a branch meant to be pushed
- `git commit` — the decision to commit is his, and he wants logical chunks
- Opening, closing, editing or commenting on a PR or an issue
- Any other change visible on GitHub
- Long-running jobs (16GB machine; the indexer OOM-killed his editor twice)

**Never:** merge. He merges. Not even when a PR is clearly ready.

**The scope of a request is exactly what it says.** "File the issue" is not
"and open a PR". "Push the fix" is not "and comment on the PR". "Do a PR" means
open one, in `.github/pull_request_template.md` format, into `develop` — it is
not standing permission to open PRs later, or to do anything beyond opening it.
Finish the thing asked for, then stop and report.

**Size is not a reason.** A one-character diff needs the same permission as a
large one. The gate is who can see the action, never how small it is.

**Never write his name, or attribute a decision to him, anywhere public.** Not
in a commit message, PR, issue or comment — not even to be transparent about
why a change was made. If something public needs explaining, draft it and let
him post it. Everything on GitHub goes out under his real name, and `gh` posts
*as him*: there is no separate bot identity.

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

Audited 2026-11-09 against the tree, not against this file's previous claims.

**Built and tested** (291 tests: 150 Python, 141 frontend): the domain model,
citation resolver, LLM gateway, prompts, LangGraph orchestrator, SSE, run
persistence, the corpus fetcher, the indexer, the frontend courtroom,
transcript, dissent log, replay and theming.

**Not built:** the evaluation runner (`run.py`, `report.py`), arm E, the case
picker, and the case fixture set (1 of a target 40–80).

**The corpus is a per-machine artifact.** `data/cache/` and `data/index/` are
gitignored (ADR 0007): the corpus travels as manifests, and each machine
resolves against whatever it last fetched. A fresh clone gets the 24-article
placeholder `setup.sh` copies from `corpus/stub/`. **Evaluation runs on
Anudveg's machine, which has the full corpus** — treaties plus the 161
customary rules.

Hamd's machine deliberately does not run the indexer: 16GB, and the embedding
stage has OOM-killed his editor. So on this machine most citations resolve
`out_of_corpus`, and that is the local index being small, not a fabrication
signal. Don't read citation statuses as signal here, and don't propose running
`make corpus` as a fix. What the local index holds:

```bash
python3 -c "import json; d=json.load(open('data/index/citation_index.json')); \
print(len(d['entries']), 'locators across', sorted(d['instruments']))"
```

See [ISSUES.md](ISSUES.md).

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
- **A manifest `status: "fetched"` describes the machine that fetched it.**
  `mark_fetched()` writes it and it is committed, so it travels; the documents
  do not. `status: "fetched"` on all 23 treaties alongside a 9-instrument local
  index is the normal state here, not a broken fetch. Check `data/cache/` and
  the index's `instruments` key for what this machine actually has.
