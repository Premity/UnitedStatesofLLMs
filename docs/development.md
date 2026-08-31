# Development guide

Everything you need to work on this repo day to day.

---

## First-time setup

```bash
make setup
```

Checks prerequisites, creates `.env`, installs Python dependencies, and installs
the git hooks. Idempotent — safe to re-run.

Then fill in `.env`:

| Key | Where to get it |
| --- | --- |
| `MISTRAL_API_KEY` | https://console.mistral.ai/ — free tier, ~1B tokens/month |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey — free tier, 100 req/day |

And pull the attacker models:

```bash
ollama pull qwen3.5:14b
ollama pull gemma3:12b
```

> No GPU? Run the containerised Ollama profile (`make up-ollama`, then set
> `COUNCIL_OLLAMA_BASE_URL=http://ollama:11434`), or point the attackers at
> Cloudflare Workers AI. See [ADR 0006](adr/0006-ollama-host-by-default.md).

---

## Daily commands

```bash
make help          # every target, self-documenting
make up            # start the dev stack
make down          # stop it
make logs          # tail everything
make logs S=api    # tail one service
make check         # lint + tests — what CI runs
```

**Dev URLs:**

| | |
| --- | --- |
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |

---

## Dev vs prod

Three compose files:

| File | Loaded | Purpose |
| --- | --- | --- |
| `docker-compose.yml` | always | Base — services, networks, volumes |
| `docker-compose.override.yml` | **automatically** | Dev — hot reload, exposed ports, bind mounts |
| `docker-compose.prod.yml` | explicitly | Prod — baked images, nothing exposed, JSON logs |

So `docker compose up` is dev with no flags, and prod is explicit:

```bash
make up          # dev
make prod-up     # prod
```

In dev, `runtime/api/app`, `prompts/`, and `council_core` are bind-mounted, so
editing Python or a prompt template reloads the server in place.

---

## The corpus

```bash
make fetch     # download what the manifests list
make index     # chunk, embed, upsert to Qdrant + write the citation index
make corpus    # both
make reindex   # drop the collection and rebuild
```

The runtime stack must be up before `make index` — the indexer writes into its
Qdrant.

> **Not yet implemented.** Both are scaffolded with the structure and TODOs in
> place; see [corpus.md](corpus.md) and [ISSUES.md](../ISSUES.md). Until they
> are done, retrieval returns nothing and every citation resolves as
> `out_of_corpus`.

Run `make reindex` whenever chunking or the embedding model changes — a
collection built with one embedding model is meaningless when queried with
another.

---

## Testing

```bash
make test        # fast, deterministic, no network
make test-cov    # with coverage
```

`make test` must never call a model or hit the network. Anything that does is
marked `@pytest.mark.live` and excluded from CI.

Two areas where tests are not optional:

- **The citation resolver** (`packages/council-core/tests/test_citations.py`).
  If it silently accepts a fabricated citation, the project's central claim is
  false.
- **Debate termination** (`runtime/api/tests/test_workflow.py`). An unbounded
  loop drains an API quota in minutes.

---

## Linting

```bash
make lint    # check
make fmt     # auto-fix and format
```

Ruff for both linting and formatting — it replaces flake8, isort, and black.
Configured in the root `pyproject.toml`. Rule groups enabled:

| Group | Catches |
| --- | --- |
| `E`,`W`,`F` | Real errors — undefined names, unused imports |
| `I` | Import ordering (auto-fixed) |
| `UP` | Outdated syntax for Python 3.12 |
| `B` | Bug patterns — mutable default args and friends |
| `SIM`, `C4` | Readability |
| `ASYNC` | **Blocking calls inside async functions** |
| `RUF` | Ruff-specific |

`ASYNC` earns its place here: the API runs an async LangGraph pipeline making
HTTP calls to four backends, and one accidental blocking call stalls everything.

Pre-commit runs `ruff check --fix` and `ruff format` on staged files, so CI is
never the first place you learn something broke.

---

## Adding to the system

### A new debate node

1. Write it in `runtime/api/app/graph/nodes/`
2. Return **only the keys it writes** — see the parallel-node trap in
   [architecture.md](architecture.md)
3. Register it in `build_graph()` in `workflow.py`
4. Restart the API (the compiled graph is a module-level singleton)

### A prompt change

Edit the file in `prompts/`. Never inline a prompt in Python — the template hash
goes into every run artifact, and a result attributed to a prompt that has
silently changed is not a result.

In dev, `prompts/` is bind-mounted, so a change reloads immediately.

### A corpus source

1. Add the entry to the right manifest in `corpus/manifests/`
2. Implement the source in `pipeline/fetcher/app/sources/`
3. `make fetch && make index`

Citation ids are **stable identifiers**. Renaming one breaks citation resolution
in every stored run artifact that referenced it.

---

## Troubleshooting

**`council-base: image not found`**
Run `make build-base`. Every service inherits from it. `make up` does this
automatically; a bare `docker compose build` does not.

**`InvalidUpdateError: Can receive only one value per step`**
A parallel node returned the full state instead of just its own keys. Both
attackers must return only `{"turns": [...], "objections": [...]}`.

**Every citation resolves as `out_of_corpus`**
`data/index/citation_index.json` is missing — the indexer has not run
successfully. Expected until the indexer is implemented.

**API cannot reach Ollama**
On Linux, the container needs `extra_hosts: host.docker.internal:host-gateway`
(already in `docker-compose.yml`). Verify Ollama is listening on all interfaces,
not just loopback: `OLLAMA_HOST=0.0.0.0 ollama serve`.

**`StructuredOutputError` from an attacker**
Small local models sometimes will not produce clean JSON. `complete_structured`
retries once with the validation error attached. Persistent failures usually
mean the model is too small — try a larger quantisation.

**Retrieval returns nothing after reindexing**
The embedding model changed between indexing and querying. Both read
`EMBEDDING_MODEL`; make sure they got the same value, then `make reindex`.

**Free-tier quota exhausted**
Gemini AI Studio allows 100 requests/day and each debate round uses one judge
call. Lower `MAX_CONCURRENT_DEBATES`, or point the judge at a local model while
developing.

---

## Evaluation

```bash
make eval                      # all four arms — SLOW, consumes quota
make eval-arm ARM=full_council # one arm
make eval-report               # rebuild the report from existing results
```

Never part of CI. See [evaluation.md](evaluation.md).
