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
- [ ] You are on a feature branch: `git checkout -b feat/first-light`

Expect **one to two days**. Most of it is step 3.

---

## Step 1 — Credentials and models (T0-1)

### 1.1 Environment

```bash
make setup
```

Then edit `.env`:

| Variable | Get it from | Free tier |
| --- | --- | --- |
| `MISTRAL_API_KEY` | console.mistral.ai | yes |
| `GEMINI_API_KEY` | aistudio.google.com | 100 req/day |

### 1.2 Pull the attacker models

```bash
ollama pull qwen3.5:14b     # doctrinal  (~9 GB)
ollama pull gemma3:12b      # evidentiary (~8 GB)
```

This is the long wait — ~17 GB total. Start it before you read anything else.

### 1.3 Prove each model works *alone*

Do not skip this. Four models failing at once is very hard to read; one failing
on its own is obvious.

```bash
ollama run qwen3.5:14b "Reply with exactly: ok"
ollama run gemma3:12b  "Reply with exactly: ok"
```

Then the two hosted models, through the same gateway the app uses:

```bash
uv run python -c "
import asyncio
from council_core.llm.client import LLMClient, ModelConfig

async def main():
    for model_id in ('mistral/magistral-medium-latest', 'gemini/gemini-2.5-pro'):
        client = LLMClient(ModelConfig(model_id=model_id), role='smoke-test')
        print(model_id, '->', await client.complete('Reply with exactly: ok'))

asyncio.run(main())
"
```

> `complete` is async, and `LLMClient` takes a `ModelConfig` rather than a bare
> model string. Role defaults live in `council_core.llm.config` — `for_role()`
> gives you the configured model for a role instead of hardcoding ids.

> **If a local model fails to load**, it is almost always RAM. A quantised 12–14B
> needs 8–10 GB resident. Close things, or swap to a smaller tag
> (`qwen3.5:7b`) and record that you did — it changes the results.

**Done when:** all four models answer. `ollama list` shows both tags.

---

## Step 2 — Stub corpus (T0-2)

Retrieval currently returns nothing, so every citation resolves
`out_of_corpus` and the dissent log is uninteresting. A hand-written index
fixes that for now. **This is throwaway** — T1 replaces it.

### 2.1 The locator format is already decided

D1 is listed as an open decision in the plan, but the code has already settled
it. `Citation.locator` in
`packages/council-core/src/council_core/models/citation.py` renders:

```
<instrument>/art.<article>      e.g.  ap_i/art.51(2)
<case_id>/para.<paragraph>      e.g.  icty_galic_tj/para.58
```

Subparagraphs are carried inside the article string, so `art.51(2)` works
without a format change. **Confirm this with the team and write ADR 0008 to
record it** — do not invent a second format.

### 2.2 Write the index

Create `data/index/citation_index.json` (gitignored). The shape is what
`JsonCorpusIndex` reads — `entries` plus `instruments`, both required:

```json
{
  "instruments": ["ap_i", "gc_iii", "gc_iv", "rome_statute"],
  "entries": {
    "ap_i/art.51(2)": {
      "text": "The civilian population as such, as well as individual civilians, shall not be the object of attack. Acts or threats of violence the primary purpose of which is to spread terror among the civilian population are prohibited.",
      "source_url": "https://ihl-databases.icrc.org/en/ihl-treaties/api-1977/article-51"
    }
  }
}
```

Add ~20 articles. **Include `ap_i/art.51(2)`** — it is what the Galić fixture
cites, so it is the one locator you are certain will come up.

Good coverage for a stub: AP I arts. 48, 51, 52, 57 (distinction,
proportionality, precautions); GC III art. 13; GC IV art. 27; Rome Statute art.
8(2)(b).

> `instruments` is what separates `unresolved` from `out_of_corpus`. An
> instrument listed there but with no matching entry means "we indexed this
> treaty, not this article" → fabrication signal. An instrument *not* listed
> means "we never indexed this" → coverage limit. Getting this wrong makes the
> fabrication metric meaningless — non-negotiable #2.

### 2.3 Check all four statuses

```bash
uv run python -c "
from pathlib import Path
from council_core.citations.resolver import CitationResolver, JsonCorpusIndex
from council_core.models.citation import Citation, CitationType

idx = JsonCorpusIndex(Path('data/index/citation_index.json'))
r = CitationResolver(index=idx)

cases = [
    ('resolved',      Citation(type=CitationType.TREATY, instrument='ap_i', article='51(2)')),
    ('unresolved',    Citation(type=CitationType.TREATY, instrument='ap_i', article='999')),
    ('out_of_corpus', Citation(type=CitationType.TREATY, instrument='hague_v', article='1')),
    ('misquoted',     Citation(type=CitationType.TREATY, instrument='ap_i', article='51(2)',
                               quoted_text='Cats are prohibited from wearing hats.')),
]
for expected, c in cases:
    got = r.resolve(c).status
    flag = 'OK ' if got == expected else 'MISMATCH'
    print(f'{flag} {c.locator():22} expected={expected:14} got={got}')
"
```

Expected output:

```
OK  ap_i/art.51(2)         expected=resolved       got=resolved
OK  ap_i/art.999           expected=unresolved     got=unresolved
OK  hague_v/art.1          expected=out_of_corpus  got=out_of_corpus
OK  ap_i/art.51(2)         expected=misquoted      got=misquoted
```

> Two things that will trip you up: the field is `type`, not `citation_type`,
> and `locator()` is a method, not a property.

**Done when:** all four statuses are produced on demand.

---

## Step 3 — First live debate (T0-3)

The long step. Build up one role at a time.

### 3.1 You need a driver script first

**There is no CLI.** The only way in is `POST /debate/stream`, which makes
iterating painful. Write `scripts/run_debate.py` that calls the graph directly:

```python
"""Drive one debate from the command line. Development aid, not a product."""

import asyncio, json
from council_core.models.debate import DebateConfig
from app.graph.workflow import compiled_graph

async def main() -> None:
    config = DebateConfig(
        question="Does a sustained campaign of sniping and shelling directed at "
                 "civilians, conducted with the primary purpose of spreading terror, "
                 "violate the laws or customs of war?",
        facts="Over roughly 23 months, forces under the accused's command conducted "
              "sniping and shelling against civilian areas of a besieged city...",
        rounds=1,          # start at 1; raise once a single round works
        max_rounds=1,
    )
    final = None
    async for chunk in compiled_graph.astream(
        {"run_id": "dev-001", "config": config, "current_round": 0},
        stream_mode="values",
    ):
        turns = chunk.get("turns", [])
        if turns:
            print(f"turn {len(turns)}: {turns[-1].role}")
        final = chunk
    print(json.dumps({"verdict": str(final.get("verdict"))}, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

Run it with the API's env:

```bash
cd runtime/api && uv run python ../../scripts/run_debate.py
```

### 3.2 Test roles individually, in this order

Do not run the whole graph yet. Each role is a module you can call directly.

| Order | Role | Watch for |
| --- | --- | --- |
| 1 | `presenter` | Does it return parseable `Argument[]` with citations? |
| 2 | `attacker_doctrinal` | **Most likely failure point.** Small models and strict JSON |
| 3 | `attacker_evidentiary` | Same, different model |
| 4 | `judge` | Does it rule on *every* objection, and emit confidence in [0,1]? |

A failure here is a prompt or a model problem, not a graph problem — much
cheaper to diagnose in isolation.

### 3.3 Then the graph, in increasing difficulty

1. **`retrieval_enabled=False`, `rounds=1`, zero attackers.** Proves the graph
   wiring, nothing else.
2. **Add retrieval.** Proves the stub index is reachable from the node.
3. **Add one attacker.** Proves the role boundary and citation grounding.
4. **Add the second attacker.** ← **This is where `InvalidUpdateError` lives.**
5. **`rounds=2`, then `rounds="auto"`.** Proves termination.

### 3.4 Failures you should expect

| Symptom | Cause | Fix |
| --- | --- | --- |
| `InvalidUpdateError: At key 'config'` | A parallel node returned more than the keys it writes | Return only `{"turns": [...], "objections": [...]}` — never `{**state, ...}`. Non-negotiable #1 |
| `StructuredOutputError` repeatedly from one attacker | Small model cannot hold the JSON schema | `complete_structured` retries once. Persistent → simplify the schema or note the model is too small. **Record this; it is a finding** |
| Every citation `out_of_corpus` | Stub index not found | Check `data/index/citation_index.json` path resolves inside the container |
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
curl -N -X POST http://localhost:8000/debate/stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"...","facts":"...","rounds":1}' \
  > runtime/frontend/src/fixtures/sample-run.json
```

The sequence must contain `start` → `turn`× → `verdict` → `done`. Include a run
with at least two objections so the dissent log has something to render, and
ideally one `unresolved` citation so the frontend can show a fabrication
visually.

**Done when:** the file exists with the full event sequence, and you have told
whoever has the frontend track.

---

## Finishing

- [ ] `make check` passes
- [ ] `scripts/run_debate.py` committed — other tracks will want it
- [ ] Live tests pass; `make test` still excludes them
- [ ] Fixture committed and the frontend owner told
- [ ] ADR 0008 written if the locator format was confirmed or changed
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
