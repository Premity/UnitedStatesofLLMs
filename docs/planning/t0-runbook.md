# T0 runbook — first light

Step-by-step instructions for getting a debate to run end to end for the first
time.

**Why this track has a runbook and the others do not:** T1–T4 are "write this
module to this contract" — the contract is the instruction. T0 is debugging
~2,900 lines of code that have never executed against a live model. Nobody knows
what breaks yet, so the value is in the *order* you try things, not in the spec.

Work through this in order. Each step ends in something you can check.

---

## Before you start

- [ ] You have read [onboarding.md](onboarding.md)
- [ ] `make check` passes — 23 tests
- [ ] You are on a feature branch

Expect **one to two days**. Most of it is step 3.

> **Steps 1 and 2 are largely done** on `feature/first-light`: the driver
> scripts exist, the citation index is committed, and ADR 0008 pins the locator
> format. Work through them anyway — they are how you verify *your* machine —
> but you are verifying, not building. Step 3 onward is the open work.

---

## Step 1 — Credentials and models (T0-1)

### 1.1 Environment

```bash
make setup
```

This also copies `corpus/stub/citation_index.json` into `data/index/`, which is
gitignored. Then edit `.env`:

| Variable | Get it from | Free tier |
| --- | --- | --- |
| `GROQ_API_KEY` | console.groq.com | yes |
| `GEMINI_API_KEY` | aistudio.google.com | 100 req/day |

> Mistral was the original presenter backend and returned 429 on the first
> request from a fresh account, so the default is now Groq. See ISSUES.md.

Then, in every shell you work in:

```bash
source scripts/dev-env.sh
```

That sets `DATA_DIR`, `PROMPTS_DIR`, `CORPUS_DIR`, points Ollama at localhost
rather than `host.docker.internal`, and sets `RETRIEVAL_BACKEND=stub`.

> **Scripts run outside Docker see no API keys.** Only Compose exports `.env`
> into the environment, and LiteLLM reads provider keys from there. Run them as
> `uv run --env-file .env python scripts/...`. `.env` lines must be
> `NAME=value`, no spaces around `=`.

### 1.2 Pull the attacker models

```bash
ollama pull qwen3.5:14b     # doctrinal  (~9 GB)
ollama pull gemma3:12b      # evidentiary (~8 GB)
```

This is the long wait — ~17 GB total. Start it before you read anything else.

> **If you cannot run these locally** — not enough RAM, no GPU, or the pull is
> impractical — you have two documented alternatives, both config-only changes
> (ADR 0002, ADR 0006):
>
> - `make up-ollama` runs Ollama in a container with a shared model store, then
>   set `COUNCIL_OLLAMA_BASE_URL=http://ollama:11434`.
> - Point the attackers at Cloudflare Workers AI — free tier is ~10,000
>   neurons/day, roughly 30 single-case runs. Set `CLOUDFLARE_API_KEY` and
>   `CLOUDFLARE_ACCOUNT_ID`.
>
> Either way, **record the models you actually ran**. A smaller tag is a valid
> development choice and an invalid silent one.

### 1.3 Prove each model works *alone*

Do not skip this. Four models failing at once is very hard to read; one failing
on its own is obvious.

```bash
uv run --env-file .env python scripts/smoke_models.py
```

This pings every role's configured model once and prints OK or FAIL per role,
so a bad key or a retired model id shows up here rather than mid-debate.

> **If a local model fails to load**, it is almost always RAM. A quantised 12–14B
> needs 8–10 GB resident. Close things, or swap to a smaller tag
> (`qwen3.5:9b`) and record that you did — it changes the results.

**Done when:** all four roles print OK.

---

## Step 2 — Citation index (T0-2)

Retrieval returns nothing until the indexer exists, so without an index every
citation resolves `out_of_corpus` and the dissent log is uninteresting.

**The index is already committed** at `corpus/stub/citation_index.json` — 24
treaty articles across AP I, GC III, GC IV and the Rome Statute. `make setup`
copies it to `data/index/citation_index.json`. This is throwaway; T1 replaces
it.

### 2.1 The locator format is settled

[ADR 0008](../adr/0008-citation-locator-format.md) records it:

```
<instrument>/art.<article>      e.g.  ap_i/art.51(2)
<case_id>/para.<paragraph>      e.g.  icty_galic_tj/para.58
```

Sub-paragraphs live inside the article string, outermost first —
`rome_statute/art.8(2)(b)(i)`. There is no separate paragraph field, and a whole
article does not resolve its paragraphs or the reverse.

### 2.2 Check all four statuses

```bash
uv run python scripts/check_resolver.py
```

Expected:

```
OK   resolved       ap_i/art.51(2)         -> resolved
OK   unresolved     ap_i/art.999           -> unresolved
OK   out_of_corpus  gc_i/art.3             -> out_of_corpus
OK   misquoted      ap_i/art.51(2)         -> misquoted
```

> `instruments` is what separates `unresolved` from `out_of_corpus`. An
> instrument listed there but with no matching entry means "we indexed this
> treaty, not this article" → fabrication signal. An instrument *not* listed
> means "we never indexed this" → coverage limit. Getting this wrong makes the
> fabrication metric meaningless — non-negotiable #2.

### 2.3 If you add entries

Copy the text **verbatim** from the source. A paraphrase makes correct
quotations resolve as `misquoted`, which reads in the metrics as the model
misquoting the law. Add to `corpus/stub/citation_index.json` (the committed
one), then re-copy into `data/index/`.

**Done when:** all four statuses print OK.

---

## Step 3 — First live debate (T0-3)

The long step. Build up one role at a time.

### 3.1 The driver scripts already exist

Three development aids, all committed. None is a product; they exist so you can
iterate without a server.

| Script | What it does |
| --- | --- |
| `scripts/smoke_models.py` | Pings each role's model once |
| `scripts/try_roles.py` | Runs **one role at a time**, saving output to `data/scratch/` |
| `scripts/run_debate.py` | Drives the whole graph and persists to `data/runs/` |

`run_debate.py` takes flags, which is what lets you climb the ladder in 3.3:

```bash
uv run --env-file .env python scripts/run_debate.py \
    --rounds 1 --max-rounds 1 --attackers doctrinal --retrieval
```

### 3.2 Test roles individually, in this order

Do not run the whole graph yet. `try_roles.py` saves each stage to
`data/scratch/`, so a later stage replays the earlier one's output instead of
paying for the model call again — this matters for the judge, which is
quota-bound.

```bash
uv run --env-file .env python scripts/try_roles.py presenter
uv run --env-file .env python scripts/try_roles.py doctrinal
uv run --env-file .env python scripts/try_roles.py evidentiary
uv run --env-file .env python scripts/try_roles.py judge
```

| Order | Role | Watch for |
| --- | --- | --- |
| 1 | `presenter` | Does it return parseable `Argument[]` with citations? |
| 2 | `attacker_doctrinal` | **Most likely failure point.** Small models and strict JSON |
| 3 | `attacker_evidentiary` | Same, different model |
| 4 | `judge` | Does it rule on *every* objection, and emit confidence in [0,1]? |

A failure here is a prompt or a model problem, not a graph problem — much
cheaper to diagnose in isolation.

### 3.3 Then the graph, in increasing difficulty

Each line is a `run_debate.py` invocation:

| # | Flags | Proves |
| --- | --- | --- |
| 1 | `--rounds 1 --max-rounds 1` | Graph wiring, nothing else |
| 2 | `… --retrieval` | The stub index is reachable from the retrieve node |
| 3 | `… --retrieval --attackers doctrinal` | Role boundary and citation grounding |
| 4 | `… --retrieval --attackers doctrinal evidentiary` | ← **`InvalidUpdateError` lives here** |
| 5 | `--rounds 2`, then `--rounds auto --max-rounds 3` | Termination |

> **Do not run step 1 without `--retrieval` and then conclude citations are
> broken.** With retrieval off, the context template tells every role to argue
> "from principle" and the presenter emits no citations at all. That run proves
> the wiring and tests no citation handling whatsoever.

### 3.4 Failures you should expect

| Symptom | Cause | Fix |
| --- | --- | --- |
| `InvalidUpdateError: At key 'config'` | A parallel node returned more than the keys it writes | Return only `{"turns": [...], "objections": [...]}` — never `{**state, ...}`. Non-negotiable #1 |
| `StructuredOutputError` repeatedly from one attacker | Small model cannot hold the JSON schema | `complete_structured` retries once. Persistent → simplify the schema or note the model is too small. **Record this; it is a finding** |
| Every citation `out_of_corpus` | Stub index not found, or `RETRIEVAL_BACKEND` unset | `source scripts/dev-env.sh`, and check `data/index/citation_index.json` exists (`make setup` copies it) |
| Debate never ends | Termination condition never fires | `max_rounds` is an absolute ceiling — if it is not stopping, that is a real bug. Non-negotiable #7 |
| Judge returns confidence `0.95` on everything | Not a bug | Expected. This is exactly what the evaluation measures |

### 3.5 Save the artifact

Once a full debate completes, confirm it persisted:

```bash
ls data/runs/ && python3 -m json.tool data/runs/*.json | head -40
```

**Done when:** `data/runs/<id>.json` exists from a real run, with a non-empty
dissent log and a verdict carrying confidence in [0,1].

---

## Step 4 — Live tests (T0-4)

The first tests that touch the network. They must not run in CI.

### 4.1 Register the marker

In the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["live: touches the network and real models (excluded from CI)"]
```

### 4.2 Write `runtime/api/tests/test_live_debate.py`

Assert the things that would silently break:

- The debate **terminates** within `max_rounds`
- The dissent log is **non-empty** (the judge ruled on something)
- Every turn carries a **prompt hash** — without it a run is not reproducible
- Confidence is **in [0,1]**
- No citation has status `None`

### 4.3 Confirm CI stays hermetic

```bash
uv run pytest -m live        # runs the live suite
make test                    # must NOT run it — still 23 tests
```

**Done when:** both commands behave as above.

---

## Step 5 — Freeze the frontend fixture (T0-5)

**This unblocks the frontend track permanently**, so do it as soon as step 3
succeeds.

Capture the SSE event sequence as the frontend will receive it:

```bash
uv run --env-file .env python scripts/record_fixture.py
```

This drives the real `/debate/stream` handler in-process — no server needed —
so the events are exactly what the frontend receives. It refuses to write a
fixture from a failed run unless you pass `--force`.

The sequence must contain `start` → `turn`× → `verdict` → `done`. Include a run
with at least two objections so the dissent log has something to render, and
ideally one `unresolved` citation so the frontend can show a fabrication
visually.

**Done when:** the file exists with the full event sequence, and you have told
whoever has the frontend track.

---

## Finishing

- [ ] `make check` passes
- [x] ~~Driver scripts committed~~ — done, `scripts/`
- [x] ~~ADR 0008 for the locator format~~ — done
- [ ] Live tests pass; `make test` still excludes them
- [ ] Fixture committed and the frontend owner told
- [ ] **Anything surprising written up** — if a model could not hold the schema,
      or the judge was uniformly overconfident, that is a result. Put it in
      [ISSUES.md](../../ISSUES.md)

Merge with `make merge-develop`.

---

## If you are stuck for more than half a day

Say so. T0 blocks the frontend track and de-risks everything else, so a stuck
T0 is the one thing in this plan worth pulling people onto.

Partial progress is still worth landing: a working presenter and a broken
attacker is a better state than an untouched repo, and tells the next person
where to look.
