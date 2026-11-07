# Known issues & pending work

Current as of 2026-11-07, after the corpus (T1), the first frontend pass (T3),
and the PR #7 review fixes (GitHub #8–#11).

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

### [RESOLVED] Judge model: Gemini was a dead end, Groq broke independence, settled on OpenRouter

`gemini/gemini-2.5-pro` returned 404 for new AI Studio users ("use
`models/gemini-3.1-pro-preview`"). Switching to it didn't help — confirmed
against a live key across checks a week and a half apart (2026-10-25 and
2026-11-03), it returns `429` with `limit: 0` for this model specifically: not
a daily quota exhausted, a standing exclusion from the free tier. The
suggested successor, `gemini-3.8-flash`, has no quota/billing block at all but
returned `503 UNAVAILABLE` ("high demand") on **every** check across the same
week and a half — not a launch-week spike, sustained unavailability. The older
`gemini-2.0-flash` and `gemini-2.5-flash` have both been retired outright and
404 straight back to `gemini-3.8-flash`. **No free Gemini path works for this
key**, full stop.

`groq/openai/gpt-oss-120b` unblocked testing but put judge in the same model
family as the presenter — any agreement between them is not independent
corroboration the way it would be across families, a real regression against
the "four different model families" design intent. Not fixed by also moving
the attackers to Groq (see below): that just meant 3 of 4 roles were one
vendor.

**Settled on `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`** — NVIDIA,
a genuinely independent fourth family from Groq (OpenAI/Qwen), reachable via
a free OpenRouter account (`OPENROUTER_API_KEY`, no payment method required
for `:free`-suffixed models). Checked directly before switching:

- Parses cleanly against the real `Verdict` schema on a realistic judge-sized
  prompt — all six fields, correctly reasoned, correctly distinguished
  distinction from proportionality.
- `reasoning` comes back as a field separate from `content` rather than
  sharing one pool the way Ollama's raw thinking block does — but this does
  **not** mean the model is exempt from the hybrid-reasoning budget problem,
  just that the failure surfaces later. A round-1-sized test prompt fit
  comfortably in the plain 4096-token default (933 reasoning tokens, 3260
  chars of content). **A real round-3 judge call did not**: the dissent log
  grows every round, so round 3's response is the largest of the debate, and
  it hit the same 4096 ceiling — empty content on the first attempt, a JSON
  response truncated right near the end on the repair attempt. Fixed by
  extending `RoleModels.for_role()`'s elevated budget (16000/600s) to
  `openrouter/nvidia/nemotron`-prefixed models too, same as Ollama and
  Gemma 4. **Confirmed working after the fix**: a full 3-round debate
  completed end to end — every role, every round, zero failures, the first
  time this session a debate has gone the full distance.
- `reasoning_effort` is listed as a supported parameter in OpenRouter's own
  catalog, but LiteLLM's OpenRouter integration rejects it for this model
  (`UnsupportedParamsError`) — not usable through this stack as installed.
- **Latency is real and prompt-dependent, not a red flag**: three trivial
  "Say OK" calls all landed in under 1.1s, a round-1-sized judge call took
  78–146s, and the round-3 call (post-fix) took longer still. Consistent with
  a large model doing proportional work, not the "fails even on hello"
  pattern that doomed Gemma 4 (see below) — but meaningfully slower than
  Groq's ~5s judge turns, extending a 3-round debate's wall time by several
  minutes just for judge calls. Judge isn't on the time-critical parallel
  path the attackers are, so this is a cost, not a correctness problem.

**[HIGH] OpenRouter's free-model daily limit is 50 requests, shared across
every `:free` model on the account** — confirmed via the key's own
introspection endpoint (`GET /api/v1/key`), not a third-party estimate:
`free_model_daily_requests: { used: 13, limit: 50, remaining: 37 }` after
today's testing. A 3-round debate uses at least 3 judge calls (more if any
repair/retry fires), capping this at roughly **16 debates/day** before the
key is throttled — and the evaluation harness (40–80 cases, ISSUES.md) would
need 120–240+ judge calls, completely infeasible on this tier alone. Fine for
continued dev/validation; not viable for a real scored run without either a
paid OpenRouter tier or swapping the judge again before that eval.

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

### [RESOLVED] `qwen3.5:9b`'s thinking mode could exhaust its own token budget

Qwen3.5 is a hybrid-reasoning model: it generates an invisible `<think>` block
before the answer (visible via Ollama's raw API as a `thinking` field;
`reasoning_content` through LiteLLM comes back `None` for this provider — it
isn't surfaced at all). On a short test prompt, `max_tokens=4096` (the
previous default) was consumed entirely by thinking, `content` came back
empty, and `complete_structured` failed with "No JSON object found."

Raising `max_tokens` to 16000 and `timeout_seconds` to 600 for every
`ollama/`-backed role (`RoleModels.for_role`) was not a reliable fix: on a
real graph run with retrieval on — a bigger prompt, real retrieved citations
to reason about — the same model burned 467s and returned nothing again, the
identical empty-content signature. The failure threshold scales with prompt
complexity, not a fixed token count, so there was no `max_tokens` ceiling that
was safe for every round of a real debate.

Superseded by moving both attackers off Ollama entirely — see the Gemma 4
entry below. `think: false` was tried as an alternative fix and rejected: it
reliably returns an empty `{"objections": []}` on every prompt tested,
including ones with real substance to object to. It looks like *wrong*, not
merely *faster*.

### [SUPERSEDED] Attackers moved from local Ollama to hosted Gemma 4, then off it again

Local Ollama models tied the attacker roles to whoever's machine was running
the stack, and qwen3.5's thinking-budget problem (above) was never fully
solved. Checked whether Google AI Studio's Gemma 4 models
(`gemma-4-31b-it`, `gemma-4-26b-a4b-it`) were reachable on the same
free-tier key already used for the judge: both are, confirmed via direct REST
calls and via LiteLLM's `gemini/` provider.

**The exact same hybrid-reasoning budget bug reproduced on the hosted API.**
At `max_tokens=4096` against a realistic attacker-sized prompt,
`gemma-4-26b-a4b-it` hit the ceiling with all 4093 completion tokens spent on
reasoning and returned empty content (`finish_reason: length`) — bit-for-bit
the qwen3.5 failure, just on a different provider. Fixed by generalizing
`RoleModels.for_role()`'s elevated budget (16000 tokens / 600s) to any
`gemini/gemma`-prefixed model, not just `ollama/`.

That fix worked, but the models themselves didn't hold up. Both return
`500 INTERNAL` and occasionally `503` ("high demand") often enough that two
separate live multi-round debates died outright after exhausting the
retry-with-backoff budget (6 attempts, ~90s span) — not a one-off: a search of
Google's AI Studio developer forum turned up the identical problem reported
independently by other developers, at a much larger scale (one report of
error rates swinging from 2–5% to 70% within a week; another of 95% failures,
including on a trivial "hello" prompt), with speculation but no confirmation
that free-tier serving of open-weight models like Gemma gets less dedicated
capacity than the proprietary Gemini line. No fix or acknowledgment from
Google as of that thread. Given that, no retry budget we pick is reliably
going to be enough — this isn't a bug our code can route around.

**Moved the attackers to Groq instead** (see entry below) rather than attempt
a Gemini->Gemma fallback or push the retry budget further. The elevated
hybrid-reasoning budget logic in `for_role()` is left in place (harmless, and
documents the lesson) even though nothing uses `gemini/gemma*` by default
any more.

### [RESOLVED] Attackers moved to Groq (`qwen3.8-27b`, `gpt-oss-20b`)

Groq hosts no Gemma models at all for this key (confirmed via its `/models`
endpoint — the catalog is OpenAI's `gpt-oss` family, Qwen's `qwen3.8-27b`, a
couple of small guard/safety models, and audio models). No like-for-like
replacement exists, so this is a deliberate pairing rather than a mechanical
swap:

- `attacker_doctrinal` -> `groq/qwen/qwen3.8-27b` (Alibaba — a different
  vendor from presenter/judge, which are both `groq/openai/gpt-oss-120b`)
- `attacker_evidentiary` -> `groq/openai/gpt-oss-20b` (same family as
  presenter/judge, smaller size)

This means 3 of 4 roles are now OpenAI-family models (just two different
sizes), which further erodes the "four different model families" design
intent beyond the presenter/judge overlap already flagged above. Attackers
sharing a vendor with the judge is lower-risk than presenter and judge
sharing one, though, since the attackers don't corroborate each other or the
verdict — they're adversarial roles, not agreeing judges. **This pairing was
a deliberate choice, not a default to leave unexamined** if a fourth
independent model family becomes available later (e.g. a working paid Claude
or Gemini judge, freeing Groq's `gpt-oss-120b` to be attacker-only).

Both models were checked against a realistic attacker-sized prompt at the
default 4096-token budget before switching: `qwen3.8-27b` completed in 745
tokens with no reasoning-token overhead recorded; `gpt-oss-20b` used 1365 of
4096 on reasoning with the rest free for content, comfortable headroom on a
single test. Not yet confirmed under round 2+ accumulated-context load, the
same caveat that applied to qwen3.5 and Gemma 4 before their own failures
surfaced — this is a single data point, not a guarantee.

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

### [RESOLVED] LiteLLM retry predicate missed `ServiceUnavailableError`

Discovered live with the new Gemma 4 attackers (above): a debate failed
outright on a single `503 Service Unavailable` ("high demand") from
`gemma-4-31b-it` — the same error signature that made `gemini-3.8-flash`
unusable for over a week. `CouncilLLM.complete()`'s retry predicate was a
fixed tuple of LiteLLM exception types (`RateLimitError`, `APIConnectionError`,
`Timeout`, `InternalServerError`), extended once already for Groq's rate
limit. `ServiceUnavailableError` isn't a subclass of any of those — it's a
sibling under `litellm.APIError` — so it fell straight through with no retry
at all.

Every LiteLLM exception sets `status_code` in `__init__` (checked against the
installed version's source for all five classes above). Replaced the type
tuple with a predicate matching on `status_code in {429, 500, 502, 503, 504}`,
plus an explicit check for `TimeoutError`/`ConnectionError`/`litellm.Timeout`
(the last sets `status_code=408`, which deliberately isn't in the retryable
set — a timeout is always worth retrying regardless of code, so it's checked
by type instead). This generalizes instead of enumerating: the predicate has
now needed extending twice for two different providers' exception subclasses,
and a code-based check closes that whole class of gap rather than the next
instance of it. Confirmed against 9 cases (5 retryable, including
`ServiceUnavailableError` and `Timeout`; 4 not, including `BadRequestError`
and `AuthenticationError`, which should fail fast rather than waste the retry
budget on a permanent error).

### [RESOLVED] Rebuttal prompt's vague schema reference produced a bare JSON array

A live debate died in round 2: the presenter (`groq/openai/gpt-oss-120b`)
returned a bare JSON array of arguments instead of the required
`{"arguments": [...]}` object, failed `_PresenterResponse` validation, failed
identically on the one repair attempt, and crashed the whole run.

Root cause: `prompts/presenter/opening.md` shows a concrete JSON example with
the `arguments` wrapper key. `prompts/presenter/rebuttal.md` — used for every
round after the first — did not; it only said "return the same JSON shape as
your opening: **a complete list of the arguments** you now stand on," which
the model read literally and returned a JSON *list*. This is the same root
cause as the `art.art.` locator bug above: the rebuttal prompt never
re-anchors the model with a worked example, so it free-associates from the
English description instead, and round 2+ carries the most accumulated
context to free-associate from. Two independent failures now trace to this
exact gap.

Fixed by giving `rebuttal.md` the same fenced JSON example `opening.md` has,
instead of a cross-reference. Worth checking whether any other
prompt template describes its schema only in prose rather than showing it —
`attacker_doctrinal/challenge.md`, `attacker_evidentiary/challenge.md`, and
`judge/rule.md` are single templates reused every round (no opening/rebuttal
split), so they don't have this specific vulnerability, but it's worth
keeping in mind for any future per-round prompt variants.

### [LOW] Blank `COUNCIL_SEED=` crashed settings

`.env.example` ships `COUNCIL_SEED=` empty, which failed integer parsing in
`RoleModels`. Fixed with `env_ignore_empty=True`.

### [LOW] Local runs need `--env-file .env`

Only Docker Compose exports `.env` into the process environment. LiteLLM reads
provider keys from the environment, so scripts run outside Docker see no keys
unless started with `uv run --env-file .env ...`. `.env` lines must be
`NAME=value` with no spaces around `=`.

---

## Found reviewing PR #7 (GitHub #8–#11)

Four issues filed against the T0 fixes above, after they were pushed for
review. All fixed; each links the GitHub issue it closes.

### [RESOLVED] Article-prefix strip mangled any value starting with 'art' (#8)

`_ARTICLE_PREFIX_RE` in `citation.py` made both the `.` delimiter and the
trailing whitespace optional, so it also matched a bare `art` with no
delimiter and stripped those three letters off any value beginning with
them — `"artifact-3"` → `"ifact-3"`, `"articles 51 and 52"` → `"s 51 and
52"`. A mangled locator cannot resolve, so a model citing multiple articles
in prose (`"articles 51 and 52"`) would be scored as fabricating authority —
exactly the false positive the function exists to prevent. No real locator
in the live corpus index was affected (checked all 1,380), so this only fired
on malformed model output, not on anything already indexed.

Fixed by requiring a delimiter: `^\s*art(?:icle)?(?:\.|\s)\s*`. Covered by
`test_article_prefix_normalization_does_not_mangle_non_prefixed_values`.

### [RESOLVED] `art. art.51(2)` doubling reached the stored field, not just `locator()` (#11, finding 1)

`_strip_article_prefix` was applied inside `Citation.locator()` only, so the
stored `article` field kept the raw `"art.51(2)"` a model sometimes echoes
from its own prose. Every renderer that reads `.article` directly instead of
calling `locator()` — the frontend's `CitationChip`, the Markdown export —
then prepended its own `"art. "` label on top, doubling to `"art.
art.51(2)"`.

Fixed by moving the normalization into a `field_validator` on `Citation.article`,
so the stored value is already clean at construction and every reader agrees.
`locator()` no longer needs to strip anything itself.

### [RESOLVED] Groq attacker models missed the reasoning-token budget they need (#9)

`RoleModels.for_role()`'s hybrid-reasoning allowlist (16000 tokens / 600s
instead of the 4096 / 180s default) matched Ollama, Gemini's Gemma models,
and OpenRouter's nemotron — not the Groq models the attackers were switched
to in the same PR (`qwen/qwen3.8-27b`, `openai/gpt-oss-20b`), which are
reasoning models too. This is the identical failure signature that already
hit qwen3.5 and Gemma 4 (both above): round 1 fits in 4096 tokens, a later
round with more accumulated context does not, and the symptom —
`StructuredOutputError` starting in round 2 or 3 — reads like "the model is
too small" rather than a budget problem.

Not a `groq/` prefix match: Groq also hosts the presenter
(`groq/openai/gpt-oss-120b`), which is not a reasoning model and does not
need the larger budget. Named the two attacker models individually instead.
Covered by `test_llm_config.py`'s table test over every shipped default,
including a non-reasoning Groq model to confirm the allowlist doesn't
accidentally widen to the whole `groq/` prefix.

### [RESOLVED] Retry backoff only reached 32s, not the ~62s it was sized for (#10)

The comment on `CouncilLLM.complete()`'s retry decorator claimed 6 attempts
at `wait_exponential(multiplier=1, min=2, max=60)` spans ~62s, sized to cross
Groq's per-minute rate-limit window. The actual sum (verified against the
installed tenacity) is 32s — `multiplier=1` produces waits of 2, 2, 4, 8, 16,
not 2, 4, 8, 16, 32. A debate hitting Groq's per-minute limit could exhaust
all 6 attempts without ever crossing the window.

Fixed by setting `multiplier=2`, which actually produces 2+4+8+16+32 = 62s —
confirmed against the same installed tenacity, not assumed from the formula.

### [RESOLVED] A stuck judge could hold a debate slot for about two hours (#11, finding 2)

`timeout_seconds` bounds one *attempt*, not the whole retry loop.
`stop_after_attempt(6)` meant a judge call that fails every attempt could
spend up to `timeout_seconds × 6` just on attempts (600 × 6 = 3600s for a
hybrid-reasoning role), plus backoff, and `complete_structured`'s one repair
attempt doubles that — close to two hours for a single stuck model, with
`MAX_CONCURRENT_DEBATES=2` meaning two stuck judges block every new debate.

Fixed by adding `ModelConfig.total_timeout_seconds`, a second ceiling wrapped
around the *entire* retry loop with `asyncio.timeout()` — independent of how
many attempts or repairs it takes. Set to 1200s for hybrid-reasoning roles,
300s otherwise, roughly bounding two full-length attempts plus backoff
instead of six. Covered by `test_llm_client.py`.

### [RESOLVED] ISSUES.md contradicted its own section heading (#11, finding 3)

The "Attackers moved to Groq" entry above ended with a leftover "New
defaults" paragraph still naming the Gemma models that section's own title
says were replaced — left behind when the section was rewritten. Deleted.

### [RESOLVED] `onboarding.md` still named the models this PR replaced (#11, finding 4)

`docs/planning/onboarding.md` named the judge as `gpt-oss-120b` and the
doctrinal attacker as `qwen3.5:9b` — both changed earlier in the same PR;
`docs/system-design.md` was updated at the time, onboarding was missed. It
also still told a new teammate to install Ollama and set `GEMINI_API_KEY`,
neither of which the current default roster needs. This is the document a
new teammate reads first, so a wrong roster there costs more than elsewhere.

Updated to the current roster (Groq for presenter + both attackers,
OpenRouter for the judge), and to note explicitly that 3 of 4 roles are now
OpenAI-family — the "four different model families" claim quoted earlier in
the same doc no longer fully holds.

### [RESOLVED] A stored objection with no `raised_by` silently defaulted to doctrinal (#11, finding 5)

`Objection.raised_by` gaining a default (above) fixed live parsing — a model
never supplies the field, `AttackerRole.run()` overwrites it with the truth
regardless. But the same default meant a **stored** artifact missing
`raised_by` would load silently as `attacker_doctrinal` instead of raising.
`independence.measure_independence` counts objections by `raised_by` to
score how differently the two attackers behave, so a mislabelled objection
would quietly skew that metric rather than error.

Fixed at the load boundary rather than the field: `RunArtifact.from_json`
now inspects the raw JSON before validating and rejects any objection — in
`state.objections`, any `turn.objections`, or `verdict.dissent` — that has no
explicit `raised_by` key. The default stays on the field itself, since that's
still what makes live parsing lenient; only loading a stored artifact is
strict. Covered by `test_run_artifact.py`.

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

### Judge model for the scored run

The judge is now `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (see the
T0 section above) — Gemini AI Studio's free tier was a dead end, not a
request-budget problem. OpenRouter's free tier caps at 50 requests/day
account-wide, roughly 16 debates/day, which covers continued dev/validation
but not a 40–80 case evaluation (120–240+ judge calls).

Options for the scored run itself: a paid OpenRouter tier, spreading the run
across multiple days, or swapping the judge to a model with more headroom
before that run starts (the roster must then freeze — see ADR 0009).

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
