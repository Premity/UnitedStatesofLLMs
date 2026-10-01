# Known issues & pending work

Current as of the initial scaffold, 2026-08-31.

---

## Not yet implemented

### [HIGH] Corpus fetcher

`pipeline/fetcher/` — structure, CLI, and manifest loading are in place; the
source parsers are not.

Needed, one module each under `app/sources/`:

- **ICRC IHL database** — treaties and customary IHL. Structured and stable;
  start here.
- **ICC** — judgments as PDFs; paragraph numbers are in the text
- **ICTY / ICTR** — judgment PDFs, large
- **ICJ** — cases and advisory opinions, largest documents
- **UN Digital Library** — resolutions

Each normalises to the document shape in [docs/corpus.md](docs/corpus.md), writes
to `data/cache/<id>.json`, and flips the manifest entry's `status` to `fetched`.

**Blocks:** everything retrieval-dependent.

---

### [HIGH] Corpus indexer

`pipeline/indexer/` — same state.

1. Read committed treaties from `corpus/` and fetched cases from `data/cache/`
2. Chunk at **citation granularity** — article for treaties, numbered paragraph
   for judgments. Not a tuning knob: token-window chunking would make
   `icty_galic_tj/para.58` unresolvable and break citation validation entirely.
3. Embed with fastembed BGE-M3
4. Upsert to Qdrant with the payload shape in docs/corpus.md
5. Write `data/index/citation_index.json` — **both** `entries` and `instruments`.
   Without `instruments`, every miss looks like fabrication and the metric is
   worthless.

**Blocks:** citation validation, retrieval, the whole evaluation.

---

### [MEDIUM] Evaluation harness runner

`evaluation/harness/` has the arms and the case schema. Missing:

- `run.py` — drives arms over cases, writes results to `data/eval/`
- Retrieval exclusion for a case's own `source_case_id`
- `metrics/report.py` — the HTML/Markdown report
- Reasoning-overlap scoring (rubric or LLM judge)

Metrics themselves (calibration, independence, citations) are implemented.

---

### [MEDIUM] Arm E — the compute-matched control

`evaluation/harness/arms.py` defines arms A–D. Arm E, the self-consistency
control, is specified but not written.

It runs the presenter alone with retrieval, samples it *n* times at a
temperature that produces genuine variation, and aggregates the samples into one
answer and one confidence. *n* is set so that total model calls match arm D on
the same case — that matching is the whole point, so it is computed from D's
actual call count, not fixed in advance.

Needed:

- An `Arm` variant carrying a sample count rather than an attacker tuple; the
  current dataclass assumes one call per role
- An aggregation rule over samples — majority vote on the outcome, with the
  agreement rate as the confidence, is the obvious starting point
- The judge runs **once** over the aggregated answer, so E's judge cost stays
  near arm B's

**Why it matters:** without E, a D-vs-B comparison cannot separate the benefit
of adversarial structure from the benefit of spending more compute, which is the
specific criticism levelled at the multi-agent debate literature. Objective 2 is
stated against this baseline, so the headline claim is unfalsifiable until E
runs.

See [docs/evaluation.md](docs/evaluation.md) for the full ladder.

---

### [MEDIUM] Evaluation case fixtures

One sample case in `evaluation/cases/dev/`. Target is 40–80, split dev /
held-out. Below ~40 the bootstrap intervals are too wide for any arm comparison
to mean anything.

Team task — see [docs/evaluation.md](docs/evaluation.md) for how to write one
without leaking the holding into the facts.

---

### [LOW] Sprite artwork

`runtime/frontend/public/sprites/README.md` has the spec. Currently coloured
plinths with role initials; the animation and state machine are done, so real
art drops into `Sprite.tsx` without touching anything else.

---

## Decisions still open

### Judge model during development

Gemini AI Studio's free tier is 100 requests/day. A full four-arm evaluation
over 60 cases exceeds that across multiple days.

Options: run the judge locally while iterating and use the API only for the
final scored run (record which — it changes the result), or spread the run
across days, or use a second key.

### Reasoning-overlap scoring

Rubric with manual scoring, or LLM-judge against `key_reasoning`? The latter is
faster but introduces a model into the measurement of models. Leaning LLM-judge
with a manually-scored subset to validate it.

### Hosted demo

Cloudflare Workers AI free tier gives ~30 single-case runs/day. Enough for a
demo, not for evaluation. No deployment target chosen yet.

---

## Watch list

Things that are correct now and easy to break later.

- **Parallel nodes must return only their own keys.** Both attackers write to
  `turns` and `objections`. Returning full state raises `InvalidUpdateError`.
- **`EMBEDDING_MODEL` must match between indexer and API.** A mismatch produces
  meaningless similarity scores with no error.
- **`unresolved` vs `out_of_corpus` must stay distinct.** Merging them makes the
  fabrication metric meaningless.
- **Citation locator formats are permanent.** They are written into every stored
  run artifact.
- **Corpus ids are permanent.** Renaming one breaks citation resolution in every
  past run.
- **Prompts must stay in `prompts/`.** Their hashes go into run artifacts; an
  inlined prompt cannot be tracked.
- **Debate termination is quota-critical.** An unbounded loop drains a free tier
  in minutes.
