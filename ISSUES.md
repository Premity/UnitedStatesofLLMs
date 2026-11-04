# Known issues & pending work

Current as of 2026-11-04, after the corpus (T1) and the first frontend pass (T3).

> **Planning this work?** These items are scheduled as tracks and tasks in
> [docs/planning/implementation-plan.md](docs/planning/implementation-plan.md).
> This file records *what* is missing; the plan records *who does it when* and
> what "done" means.

| Item below | Track |
| --- | --- |
| Corpus fetcher | T1-2, T1-3 |
| Corpus indexer | T1-4, T1-5, T1-6 |
| Evaluation harness runner | T4-1, T4-2, T4-3 |
| Arm E — the compute-matched control | T2-4, T2-5 |
| Evaluation case fixtures | TF |
| Sprite artwork | T3 stretch |
| Courtroom staging and background | T3 stretch |
| Case picker for the question form | T3 / TF |

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

See **Courtroom staging** below for the layout this is blocked behind, and for
the licensing constraint on any background image.

---

## Found during first light (T0)

Things the first live runs turned up, 2026-10-22 through 2026-11-03. Each
changes either what runs or what the results mean.

### [HIGH] Judge model: the whole Gemini free tier turned out to be a dead end

`gemini/gemini-2.5-pro` returned 404 for new AI Studio users ("use
`models/gemini-3.1-pro-preview`"). Switching to it didn't help — confirmed
against a live key across checks a week and a half apart (2026-10-25 and
2026-11-03), it returns `429` with `limit: 0` for this model specifically: not
a daily quota exhausted, a standing exclusion from the free tier. The
suggested successor, `gemini-3.8-flash`, has no quota/billing block at all but
returned `503 UNAVAILABLE` ("high demand") on **every** check across the same
week and a half — not a launch-week spike, sustained unavailability. The older
`gemini-2.0-flash` and `gemini-2.5-flash` have both been retired outright and
404 straight back to `gemini-3.8-flash`.

**No free Gemini path currently works for this key.** Judge is now
`groq/openai/gpt-oss-120b` — the same model as the presenter — purely to
unblock testing the graph. This is a real regression against the "four
different model families" design (ADR intent): presenter and judge are now
identical, so any agreement between them is not independent corroboration the
way it would be across model families. **Do not use this pairing for a scored
run.** Before that: either re-check Gemini (a provisioning fix on Google's side
could resolve the `limit: 0` silently), or set `COUNCIL_JUDGE_MODEL` to a paid
model from a fourth family (Claude Sonnet 5.5 was costed out at ~$3–45 for the
full 40–80 case eval and is the likely candidate). Whichever model is used,
record it with the results: the judge sets every confidence the calibration
metrics score, so a judge swap mid-run makes the calibration numbers
incomparable.

### [MEDIUM] Presenter moved from Mistral to Groq

Mistral returned 429 on the first request from a fresh free-tier account.

Settled by [ADR 0009](docs/adr/0009-presenter-on-groq.md): the presenter is
**`groq/openai/gpt-oss-120b`**, one pinned id. During T0 the two machines ran
different Groq models, which are different families and not comparable — if you
have results from `llama-3.3-70b-versatile`, they were produced on a different
system under test.

The roster is frozen from the start of the scored run until it finishes.

### [MEDIUM] Retrieval off means no citations at all

With `retrieval_enabled=False` the context template tells every role to argue
"from principle", so the presenter emitted zero citations and nothing was
resolved. A T0 run with retrieval off proves the wiring but exercises no
citation checking.

T1 has since built the real corpus, so run with `--retrieval` against Qdrant.
`RETRIEVAL_BACKEND=stub` remains as a way to work without Qdrant running: it
serves word-overlap matches from the citation index, which is not semantic
search and must never be used for a scored run. It logs a warning on every
call so a stray one is visible in the output.

### [RESOLVED] Doctrinal attacker default pointed at a tag that does not exist

`ollama/qwen3.5:14b` was the configured default in `RoleModels`,
`.env.example`, and throughout the docs. Qwen3.5 has no 14b release — Ollama's
library only ships `0.8b / 2b / 4b / 9b / 27b / 35b / 122b`. `ollama pull
qwen3.5:14b` fails outright with "pull model manifest: file does not exist";
it was never a matter of one machine drifting from another.

Changed the default to `ollama/qwen3.5:9b` — closest in weight class to
`gemma3:12b`, the other attacker, keeping the two attackers comparably sized
for the independence metric. Still record the resolved model id with any
result, per `RunMetadata.role_models` — that discipline stays right even
though the original reason for writing it down here was wrong.

### [RESOLVED] Every attacker turn failed: `Objection.raised_by` had no default

`Objection.raised_by: Role` was required with no default, but neither
attacker prompt's JSON example shows that field — a model following the
prompt exactly always omits it, `_AttackerResponse` validation always failed,
and the one repair attempt failed the same way. Confirmed live: the doctrinal
attacker never once returned valid structured output before this fix.

`AttackerRole.run()` already overwrites `raised_by` unconditionally after
parsing (`roles/attacker.py`) — the model's value, if any, was never used. So
a default is free: added `default=Role.ATTACKER_DOCTRINAL` to the field with
a docstring explaining it's a placeholder that is always replaced, never a
real value. Fixed in `models/debate.py`.

### [HIGH] `qwen3.5:9b`'s thinking mode can exhaust its own token budget

Qwen3.5 is a hybrid-reasoning model: it generates an invisible `<think>` block
before the answer (visible via Ollama's raw API as a `thinking` field;
`reasoning_content` through LiteLLM comes back `None` for this provider — it
isn't surfaced at all). On a short test prompt, `max_tokens=4096` (the
previous default) was consumed entirely by thinking, `content` came back
empty, and `complete_structured` failed with "No JSON object found."

Raised `max_tokens` to 16000 and `timeout_seconds` to 600 for every
`ollama/`-backed role (`RoleModels.for_role`). Confirmed this produces two
substantive, correctly-reasoned objections on an ungrounded test prompt
(~6,300 completion tokens, ~354s). **It is not a reliable fix.** On a real
graph run with retrieval on — a bigger prompt, real retrieved citations to
reason about — the same model burned 467s and returned nothing again, the
identical empty-content signature. The failure threshold scales with prompt
complexity, not a fixed token count, so there may be no `max_tokens` ceiling
that is safe for every round of a real debate (context accumulates round over
round, so later rounds are the most at risk).

Open. Options, not yet decided: raise the ceiling further (diminishing
returns, and per-call latency is already 6–8 minutes); disable thinking
outright via Ollama's `think: false` (tested — reliably fast, but the model
then returns an empty `{"objections": []}` on every prompt tried, including
ones with real substance to object to: it looks like *wrong*, not merely
*faster*, and should not be shipped without separately verifying it against
several real prompts); or swap the doctrinal attacker to a non-hybrid-reasoning
model.

### [RESOLVED] SSE frame separator mismatch silently broke the frontend

`sse-starlette`'s default frame separator is `\r\n\r\n`. The frontend splits
incoming frames on `\n\n` (`useDebateStream.ts`), which never matches —
confirmed directly against the installed `sse-starlette` version. Every event
stayed buffered for the whole debate and nothing rendered live; the buffer
was then discarded at `done`. The backend was never broken — a real debate ran
to completion and saved a correct artifact throughout — the browser would just
never have shown any of it.

Fixed server-side: `EventSourceResponse(events(), sep="\n")` in
`routers/debate.py`. Verified against a live request — raw bytes now contain
`\n\n` exactly where the frontend's parser expects it.

### [LOW] Blank `COUNCIL_SEED=` crashed settings

`.env.example` ships `COUNCIL_SEED=` empty, which failed integer parsing in
`RoleModels`. Fixed with `env_ignore_empty=True`.

### [LOW] Local runs need `--env-file .env`

Only Docker Compose exports `.env` into the process environment. LiteLLM reads
provider keys from the environment, so scripts run outside Docker see no keys
unless started with `uv run --env-file .env ...`. `.env` lines must be
`NAME=value` with no spaces around `=`.

---

## Found while building the corpus (T1)

Eleven problems, written up with causes and fixes in
[docs/corpus-findings.md](docs/corpus-findings.md). Eight of them produced
plausible wrong output rather than an error, which is the failure mode this
project can least afford.

The ones that are still open rather than fixed:

- **Three Rome Statute weapons amendments are not indexed.** The source gives
  the inserted sentence with no article number, and a guessed locator is
  indistinguishable from a fabrication. A citation to one resolves
  `unresolved`, which the metrics read as fabrication — state it in the report.
- **UN resolutions are scanned images** in the UN Digital Library, with no
  text layer. Only the resolutions the ICRC serves as structured text are in
  scope.

---

## Frontend (T3) — open after the first pass

The courtroom, transcript, record, replay and theming are built and tested
(117 frontend tests). What follows is what was raised while looking at the
running UI and has not been done.

### [MEDIUM] Courtroom staging

Three changes, which interact and are best done in this order:

1. **A subtitle band under the courtroom**, replacing the floating speech
   bubble. The bubble is capped at `max-w-md` and occludes the scene; a claim
   of two or three lines gets cramped. A fixed-height band has the full width,
   gives the role name a stable place, and can say what is being waited on
   during a long generation. `SpeechBubble` already carries an unused `side`
   prop from an earlier attempt at this.

2. **Judge at the back, counsel flanking, presenter centred.** The present
   layout puts all three counsel in a row, which does not read as a courtroom.
   The presenter at centre also expresses the geometry of the thing: it is the
   role being attacked from both sides. Fix which attacker sits on which side
   and keep it stable across runs.

3. **Localise the objection flourish to the objecting sprite** rather than
   taking the whole courtroom. Depends on (1): once the burst is sprite-sized
   the objection's text has to live in the band. The loud/quiet distinction
   already built still applies — quiet becomes "sprite flashes, band updates".

### [MEDIUM] Courtroom background art

**No usable image yet.** Two candidates were proposed and both were the Ace
Attorney courtroom, © Capcom — the second with the watermark cropped out,
which removes copyright management information and makes it worse rather than
better. This repository is public; shipping either is infringement.

Options, in the order worth trying:

- **Build the room in SVG.** Panelling, benches and columns are gradients and
  rectangles. It themes with the palette, which a fixed image cannot — there
  are four palettes and a warm-gold photograph fights Tribunal and Oak. Scales
  to any aspect, costs a few KB, and sprite anchors become real coordinates
  rather than percentages tuned to one picture.
- **Genuinely free sources**, checking the licence on each file's own page:
  [Openclipart](https://openclipart.org) (CC0 site-wide),
  [Wikimedia Commons](https://commons.wikimedia.org) (per-file; some are
  CC BY-SA and need attribution). Search "courtroom interior", not "courtroom",
  or the results are gavels and scales.
- Commission or draw one.

Note that "free" and "royalty-free" on the stock sites are not "free to
redistribute", which is what committing to a public repo does.

A fixed-ratio background also constrains the layout: the panel can no longer
grow with its content, and every sprite position becomes an offset tuned to
one image.

### [MEDIUM] Case picker for the question form

`evaluation/cases/dev/*.json` holds prepared cases — question, facts, and the
tribunal's actual holding — but nothing exposes them to the UI, so a question
has to be typed by hand. Two constraints:

- **The case file contains the ground truth.** `holding`, `outcome` and
  `key_reasoning` must never reach the browser, or the demo shows the answer
  next to the question.
- `runtime/api` does not depend on `evaluation`; both depend only on
  `council-core`. A case endpoint either inverts that or duplicates the
  loader. Worth an ADR.

### [LOW] `role_started` stream event

`NEXT_ROLES` in `courtStore.ts` duplicates `build_graph()` to infer which
model is generating, because the stream carries only completed turns. It works
and is tested, but it is a second copy of the graph's shape that nothing keeps
in sync. A `role_started` event would remove the duplication.

### [LOW] Objection severity

`isLoud()` decides which objections earn the full flourish from whether every
citation resolved — the strongest signal available, but an inference. An
`Objection` carries no severity, and adding one would also give the evaluation
metrics something to weigh objections by.

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
