# Implementation plan

Five tracks, ~25 tasks. Four people, three weeks, everyone able to work on
anything.

New here? Read [onboarding.md](onboarding.md) first.

---

## How to read this

Work is organised into **tracks** that run in parallel, not phases that run in
sequence. Tracks are not job titles — claim tasks from whichever track is
unblocked.

Every task has four fields:

| Field | Means |
| --- | --- |
| **Depends on** | Must be `done` before this starts. Unmet → pick something else. |
| **Touches** | Files this task writes. If someone else is in them, coordinate first. |
| **Done when** | A command that passes or a file that exists. Not an adjective. |
| **Size** | `S` ≈ half a day · `M` ≈ 1 day · `L` ≈ 2 days |

A task is done when its **Done when** passes. Not when the code is written.

### Task states

Track status in standup, not in this file. This file describes the work; it is
not a status board.

---

## Track map

```
  T0  First light ──────┬──────────────────────────────► unblocks T3, T4
                        │
  T1  Corpus ───────────┼──────────────────────────────► feeds the scored run
                        │
  T2  Metrics + Arm E ──┤  (independent from day 1)
                        │
  T3  Frontend ─────────┘  (needs one artifact from T0)

  T4  Harness + run ────────────────────────────────────► needs T0, T1, T2

  TF  Fixtures ─────────────────────────────────────────► everyone, continuous
```

| Track | Delivers | Blocked by |
| --- | --- | --- |
| **T0** First light | One real debate, end to end | nothing |
| **T1** Corpus | Treaties fetched, chunked, indexed | nothing |
| **T2** Metrics + Arm E | Tested metrics, fifth arm | nothing |
| **T3** Frontend | Verified UI, component tests | T0-3 |
| **T4** Harness | `run.py`, report, the scored run | T0, T1, T2 |
| **TF** Fixtures | 40–80 cases | nothing |

**Start on day 1:** T0, T1, T2, TF. T3 after T0-3 lands (~day 2).

---

## Decisions that must be made before code

Each is a real choice someone could reasonably make differently, and each
becomes permanent once data is written. **Make these as a group, record as an
ADR, then write the code.** Guessing on day 4 is how you get stuck with it.

| # | Decision | Blocks | Owner track |
| --- | --- | --- | --- |
| **D1** | Citation locator format | All of T1 | T1 |
| **D2** | Chunk payload shape in Qdrant | T1-4 | T1 |
| **D3** | Arm E aggregation rule | T2-4 | T2 |
| **D4** | Fixture difficulty labels | TF | TF |

### D1 — the locator format

The sharpest of the four and the first thing T1 must settle.

Evidence already in the repo: `evaluation/cases/dev/icty_galic_terror.json`
cites **"Article 51(2) AP I"** — a *subparagraph*. So the format must address
subparagraphs, not just articles. If `ap_i/art.51` is the finest granularity we
index, that citation cannot resolve, and it will be reported as `unresolved` —
which reads as fabrication and poisons the headline metric.

Settle: separator, case, how subparagraphs and sub-subparagraphs are expressed,
and what a judgment paragraph looks like. Then write
[ADR 0008](../adr/).

> **This format is permanent.** It is written into every stored run artifact.
> See non-negotiable #5 in [CLAUDE.md](../../CLAUDE.md).

---

## T0 — First light

**Goal:** prove the debate graph runs against four live models.

Why this is first: ~2,900 lines of domain and orchestration code have never
executed against a real model. If the parallel fan-in breaks, or a 12B model cannot produce
parseable JSON reliably, we want to know on day 2 — not on day 9 with corpus
work built on top.

### T0-1 · Working credentials and models — `S`

- **Depends on** nothing
- **Touches** `.env` (local only, never committed)
- **Done when** `make check` passes, `ollama list` shows `qwen3.5:14b` and
  `gemma3:12b`, and both API keys are set

### T0-2 · Stub corpus for retrieval — `S`

A hand-written citation index of ~20 articles, enough to make retrieval return
something real. Throwaway: T1 replaces it.

- **Depends on** D1 (locator format)
- **Touches** `data/index/citation_index.json` (gitignored), one fixture helper
- **Done when** the citation resolver returns `resolved` for a known locator and
  `unresolved` for a fabricated one, against this index

### T0-3 · First live debate — `M`

- **Depends on** T0-1, T0-2
- **Touches** possibly `runtime/api/app/graph/*`, `runtime/api/app/roles/*`
- **Done when** `data/runs/<id>.json` exists from a real run, containing a
  non-empty dissent log and a verdict with a confidence in [0,1]

> Expect failures here — that is the point of the task. Likely candidates:
> `InvalidUpdateError` on the attacker join, `StructuredOutputError` from the
> local models, SSE disconnects. Each one found here is cheap.

### T0-4 · Live test suite — `M`

The first tests that touch the network. Marked `@pytest.mark.live` and excluded
from CI, so `make test` stays hermetic.

- **Depends on** T0-3
- **Touches** `runtime/api/tests/test_live_debate.py` (new),
  `pyproject.toml` (marker registration)
- **Done when** `uv run pytest -m live` runs a full debate and asserts
  termination, a non-empty dissent log, and every turn carrying a prompt hash;
  `make test` still excludes them

### T0-5 · Recorded fixture for the frontend — `S`

Freeze one real run as a replay fixture. This is what unblocks T3 permanently.

- **Depends on** T0-3
- **Touches** `runtime/frontend/src/fixtures/sample-run.json` (new)
- **Done when** the file exists and contains the full SSE event sequence
  (`start` → `turn`× → `verdict` → `done`)

---

## T1 — Corpus

**Goal:** the eight treaties, fetched, chunked at citation granularity, indexed.

**Scope call: treaties only for v1.** Eight structured instruments from one
source (ICRC), versus eight case PDFs from four tribunals with different
layouts. Treaties alone prove citation resolution end to end, and the Galić
fixture cites AP I — which is in the treaty set. Cases are a stretch goal.

### T1-1 · Decide the locator format (D1) — `S`

- **Depends on** nothing
- **Touches** `docs/adr/0008-citation-locator-format.md` (new)
- **Done when** the ADR is merged and `test_locator_formats_are_stable` is
  extended to cover subparagraph locators

### T1-2 · ICRC source parser — `L`

- **Depends on** T1-1
- **Touches** `pipeline/fetcher/app/sources/icrc.py` (new),
  `pipeline/fetcher/app/parsers/treaty.py` (new)
- **Done when** all 8 instruments in `corpus/manifests/treaties.json` fetch to
  `data/cache/<id>.json`, each with ≥1 article, and manifest `status` flips to
  `fetched`

### T1-3 · Fetcher tests — `M`

- **Depends on** T1-2
- **Touches** `pipeline/fetcher/tests/` (new)
- **Done when** parser tests run against **saved HTML fixtures, not the
  network**, and `make test` still passes with no network access

### T1-4 · Chunking at citation granularity — `L`

The correctness-critical task of this track.

- **Depends on** T1-1, T1-2
- **Touches** `pipeline/indexer/app/chunking/` (new)
- **Done when** GC III Article 13 and AP I Article 51(2) each produce a chunk
  whose locator round-trips through the resolver, proven by test

### T1-5 · Embed and upsert — `M`

- **Depends on** T1-4, D2 (payload shape)
- **Touches** `pipeline/indexer/app/embeddings/`, `pipeline/indexer/app/index/`
- **Done when** `make index` populates `ihl_corpus` and a semantic query for
  "attacks intended to terrorise civilians" returns AP I Art 51(2) in the top 5

### T1-6 · Citation index — `M`

- **Depends on** T1-4
- **Touches** `pipeline/indexer/app/index/citation_index.py` (new)
- **Done when** `data/index/citation_index.json` contains **both** `entries` and
  `instruments`, and a citation to a real-but-unindexed instrument resolves
  `out_of_corpus` rather than `unresolved`

> `instruments` is what makes that distinction possible. Without it every miss
> looks like fabrication. See non-negotiable #2.

### T1-7 · End-to-end corpus test — `M`

- **Depends on** T1-5, T1-6
- **Touches** `pipeline/indexer/tests/test_end_to_end.py` (new)
- **Done when** fetch → chunk → embed → index runs on 2 instruments and all four
  citation statuses are produced by a crafted input

---

## T2 — Metrics and Arm E

**Goal:** the numbers in the final report are provably correct.

292 lines of metric code currently have **zero tests**. These produce every
number the report will contain. Fully independent of other tracks — start day 1.

### T2-1 · Calibration metric tests — `M`

- **Depends on** nothing
- **Touches** `evaluation/tests/test_calibration.py` (new)
- **Done when** Brier, ECE and overconfidence match hand-computed values on at
  least three worked examples, including the degenerate cases (all-correct,
  all-wrong, single bin)

### T2-2 · Citation metric tests — `S`

- **Depends on** nothing
- **Touches** `evaluation/tests/test_citation_metrics.py` (new)
- **Done when** a test proves `unresolved` and `out_of_corpus` are counted
  **separately** and that fabrication rate ignores `out_of_corpus` entirely

### T2-3 · Independence metric tests — `S`

- **Depends on** nothing
- **Touches** `evaluation/tests/test_independence.py` (new)
- **Done when** Jaccard overlap is verified on identical, disjoint and partial
  objection sets

### T2-4 · Decide the Arm E aggregation rule (D3) — `S`

- **Depends on** nothing
- **Touches** `docs/adr/0009-self-consistency-arm.md` (new)
- **Done when** the ADR states the sampling temperature, how *n* is derived from
  arm D's call count, and the aggregation rule (majority vote with agreement
  rate as confidence is the obvious start)

### T2-5 · Implement Arm E — `L`

- **Depends on** T2-4
- **Touches** `evaluation/harness/arms.py`, `evaluation/harness/sampling.py` (new)
- **Done when** `self_consistency` appears in the arm registry, its *n* is
  computed from D's call count on the same case, and a test asserts total model
  calls match D within ±1

> The current `Arm` dataclass assumes one call per role. This needs a variant
> carrying a sample count. The judge still runs **once**, over the aggregated
> answer — so E's judge cost stays near arm B's.

---

## T3 — Frontend

**Goal:** prove the UI works against real data, and test it.

The frontend is **complete but unverified** — every component written, never run
against a real stream. This track is verification, not construction.

### T3-1 · Replay harness — `M`

A mock SSE server that replays the recorded fixture. After this, T3 never waits
on the backend again.

- **Depends on** T0-5
- **Touches** `runtime/frontend/src/mocks/` (new), `vite.config.ts`
- **Done when** `npm run dev:mock` drives the full UI from the fixture with no
  API running

### T3-2 · Verify the courtroom — `M`

- **Depends on** T3-1
- **Touches** `runtime/frontend/src/components/courtroom/*`
- **Done when** turns animate in order, the speaking role is visually distinct,
  objections flourish, and the sequence is watchable start to finish without
  visual glitches

### T3-3 · Verify the dissent log — `M`

- **Depends on** T3-1
- **Touches** `runtime/frontend/src/components/dissent/*`,
  `runtime/frontend/src/components/citations/*`
- **Done when** overruled objections render with the judge's reason, and all
  four citation statuses are visually distinguishable — `unresolved` must not
  look like `out_of_corpus`

### T3-4 · Failure states — `M`

- **Depends on** T3-1
- **Touches** `runtime/frontend/src/hooks/useDebateStream.ts`
- **Done when** a mid-stream `error` event, a dropped connection, and a debate
  that terminates on `max_rounds` each render something sensible rather than
  hanging

### T3-5 · Component tests — `L`

- **Depends on** T3-2, T3-3, T3-4
- **Touches** `runtime/frontend/src/**/*.test.tsx` (new), `package.json`
- **Done when** `npm test` passes in CI and covers the store reducer, the stream
  hook, and citation-status rendering

### T3-6 · Export the dissent log — `M`

- **Depends on** T3-3
- **Touches** `runtime/frontend/src/components/dissent/*`, export renderer
- **Done when** a completed run downloads as a readable document that leads with
  the overruled objections

---

## T4 — Harness and the scored run

**Goal:** run the ablation and produce defensible numbers.

### T4-1 · `run.py` — `L`

- **Depends on** T0-3, T2-5
- **Touches** `evaluation/harness/run.py` (new)
- **Done when** `make eval-arm ARM=rag` runs that arm over the dev case and
  writes a result to `data/eval/`

### T4-2 · Retrieval exclusion — `M`

A case whose own judgment is in the corpus must not retrieve it, or the system
reads the answer back.

- **Depends on** T4-1
- **Touches** `evaluation/harness/run.py`, `runtime/api/app/services/retrieval.py`
- **Done when** a test proves a case with `source_case_id` set never retrieves
  that document

### T4-3 · Report generation — `M`

- **Depends on** T4-1
- **Touches** `evaluation/metrics/report.py` (new)
- **Done when** `make eval-report` produces a Markdown report with per-arm
  metrics and bootstrap 95% confidence intervals

### T4-4 · Local-judge rehearsal — `M`

A full 5-arm run with the judge pointed at a local model. Costs no quota and
finds the breakages before they cost quota.

- **Depends on** T4-1, T4-3, T1-7, ≥10 fixtures
- **Touches** config only
- **Done when** all five arms complete over ≥10 cases with no crash, and the
  report renders

### T4-5 · The scored run — `L`

- **Depends on** T4-4, TF complete
- **Touches** `data/eval/`, `evaluation/reports/`
- **Done when** all five arms have run over the held-out set with the API judge,
  and the report records which judge backend was used

> **This is quota-bound, not effort-bound.** 100 judge requests/day. See
> [timeline.md](timeline.md) for the booking schedule.

---

## TF — Fixtures

**Everyone, continuously, from day 1.** ~15 cases each.

This is the critical path. It is the only item that cannot be compressed by
adding effort at the end, and the only one where four people genuinely beat one
person working four times as long.

A rushed fixture with the holding leaked into the facts **silently inflates
every arm's accuracy**, and you will not catch it from the numbers.

### TF-1 · Agree the difficulty rubric (D4) — `S`

- **Depends on** nothing
- **Touches** [fixtures-guide.md](fixtures-guide.md)
- **Done when** `easy` / `medium` / `hard` have written criteria and two people
  independently label the same three cases identically

### TF-2 · Dev set — 20 cases — `L`

- **Depends on** TF-1
- **Touches** `evaluation/cases/dev/`
- **Done when** 20 cases validate against the schema and a second person has
  reviewed each for holding-leakage

### TF-3 · Held-out set — 20–60 cases — `L`

- **Depends on** TF-1
- **Touches** `evaluation/cases/held_out/`
- **Done when** validated, reviewed, and **never opened during development**

### TF-4 · Fixture validator — `M`

- **Depends on** TF-1
- **Touches** `evaluation/tests/test_fixtures.py` (new)
- **Done when** `make test` fails on a malformed fixture, a missing required
  field, or an unknown difficulty label

> A validator cannot detect holding-leakage — that needs human review. It
> catches everything mechanical, which frees review for the thing that matters.

---

## Integration points

Parallel tracks still have to meet. These are the moments where they do.

| # | Where | Between | What must be agreed |
| --- | --- | --- | --- |
| **I1** | Locator format | T1 → T0, T4 | D1 settled before T0-2 writes the stub index |
| **I2** | Recorded fixture | T0 → T3 | SSE event sequence frozen: `start` / `turn` / `verdict` / `error` / `done` |
| **I3** | Citation index shape | T1 → T4 | `entries` + `instruments` both present |
| **I4** | Arm registry | T2 → T4 | Arm E in the registry before `run.py` iterates arms |

---

## Definition of done — all tracks

A task is not done until **all** of these hold:

- [ ] Its **Done when** command passes
- [ ] `make check` passes
- [ ] New behaviour has a test; new network behaviour is marked `@pytest.mark.live`
- [ ] Any trade-off decision is recorded in an ADR
- [ ] Conventional Commit, merged via `make merge-develop`
- [ ] No new silent-failure mode, or it is added to the register in
      [system-design.md §11.2](../system-design.md)

---

## If a track runs early

Three weeks for ~140 hours of work across four people means someone will run
dry. In rough priority:

1. **Write more fixtures.** Absorbs unlimited help, improves every result.
2. **Tier 2 cases** — the 8 tribunal judgments T1 deferred. Real stretch value.
3. **Frontend polish** — real sprite artwork replacing the placeholder plinths.
4. **Raise the bootstrap sample count** in the report.

---

## If a track runs late

Decide the fallback now, not on day 19.

| Track | Fallback |
| --- | --- |
| **T1 corpus** | Hand-built index of ~20 articles. Enough to demonstrate all four citation statuses; not enough for a corpus-coverage claim. Say so in the report. |
| **T2 Arm E** | Report D-vs-B with the compute confound stated as a limitation. **Do not claim a control that did not run.** |
| **TF fixtures** | Run on fewer cases and report wider intervals. An honest wide interval beats a narrow one computed on 12 cases. |
| **T3 frontend** | Demo from the recorded fixture rather than live. |
| **T4 scored run** | Report the local-judge rehearsal, clearly labelled as such. |
