# Data model

Every domain type and how they relate. Definitions live in
`packages/council-core/src/council_core/models/`.

---

## Relationships

```
RunArtifact
├── RunMetadata          provenance: models, temperatures, prompt hashes, tokens
└── DebateState          the debate — and, once complete, the dissent log
    ├── DebateConfig     what was asked and how
    ├── context          ResolvedCitation[]  — retrieved corpus spans
    ├── turns            Turn[]              — every model invocation
    ├── arguments        Argument[]          — from the presenter
    ├── objections       Objection[]         — from the attackers
    └── verdict          Verdict
        └── dissent      Objection[]         — the overruled ones
```

`DebateState` is not a summary written after the fact. It is the live LangGraph
state object, and when the run ends it *is* the record.

---

## Citations

### `Citation`

What a model emits. Structured, never prose — that is what makes fabrication
detectable.

| Field | Type | Notes |
| --- | --- | --- |
| `type` | `CitationType` | `treaty` \| `case` \| `customary` \| `resolution` |
| `instrument` | str | Canonical slug: `rome_statute`, `gc_iv`, `ap_i` |
| `article` | str? | Treaties: `"8(2)(b)(iv)"` |
| `case_id` | str? | Cases: `"icty_galic_tj"` |
| `paragraph` | str? | Cases: `"58"` |
| `rule_number` | int? | Customary IHL: 1–161 |
| `quoted_text` | str? | Checked against the source span when present |

`locator()` renders the identity used in logs, exports, and metrics:

| Type | Format |
| --- | --- |
| Treaty | `rome_statute/art.8(2)(b)(iv)` |
| Case | `icty_galic_tj/para.58` |
| Customary | `customary_ihl/rule.14` |

> **Locator formats are permanent.** They are written into every stored run
> artifact. Changing one invalidates citation resolution for all past runs.

### `ResolvedCitation`

A citation after validation. Also the type retrieved corpus spans come back as,
so context and cited authority share one shape end to end.

| Field | Notes |
| --- | --- |
| `citation` | The original |
| `status` | `resolved` \| `unresolved` \| `out_of_corpus` \| `misquoted` |
| `corpus_text` | Authoritative text, when resolved |
| `source_url` | Public source link |
| `note` | Why resolution failed |

`is_supported` is true only for `resolved`.

---

## The debate

### `Role`

| Value | Mandate |
| --- | --- |
| `presenter` | Argues the position; sets the quality ceiling |
| `attacker_doctrinal` | Challenges legal characterisation |
| `attacker_evidentiary` | Challenges factual predicate |
| `judge` | Rules on objections, calibrates confidence |
| `retriever` | Not a debater; grounds the others |

### `Argument`

| Field | Notes |
| --- | --- |
| `id` | `arg_<8 hex>` — objections target this |
| `claim` | One contestable proposition |
| `reasoning` | Why it follows from the authority |
| `citations` | As emitted |
| `resolved_citations` | Filled at the role boundary |

`is_grounded` — true when at least one citation resolved. An ungrounded argument
is not necessarily wrong, but the judge is told it is unsupported.

### `Objection`

| Field | Notes |
| --- | --- |
| `id` | `obj_<8 hex>` |
| `raised_by` | Overwritten with the true role after parsing, so a model cannot misattribute |
| `target_argument_id` | Which argument is challenged |
| `ground` | One sentence |
| `reasoning` | The full challenge |
| `disposition` | Set by the judge |
| `disposition_reasoning` | **The dissent log entry.** Required for overruled objections |

### `ObjectionDisposition`

| Value | Meaning |
| --- | --- |
| `sustained` | Defeated or materially weakened the argument |
| `overruled` | Rejected — **goes into the dissent log** |
| `partial` | Narrowed without defeating |
| `unaddressed` | The judge did not reach it — a gap, surfaced not hidden |

### `Turn`

One model invocation and everything it produced. Carries `model_id`,
`prompt_id`, `prompt_hash`, timing, and token counts — the unit the frontend
streams and the artifact records.

### `Verdict`

| Field | Notes |
| --- | --- |
| `conclusion` | The holding |
| `reasoning` | How surviving arguments support it |
| `confidence` | 0.0–1.0, scored by Brier in the harness |
| `confidence_reasoning` | Why that number — guards against unexamined certainty |
| `surviving_argument_ids` | Which arguments stood |
| `dissent` | **The headline output** — overruled objections with reasons |

### `DebateConfig`

| Field | Default | Notes |
| --- | --- | --- |
| `question` | required | |
| `facts` | `""` | |
| `rounds` | `"auto"` | Fixed int, or judge-terminated |
| `max_rounds` | `3` | Hard ceiling, 1–5 |
| `enabled_attackers` | both | Ablation arms vary this |
| `retrieval_enabled` | `true` | False for arm A |
| `top_k` | `8` | |

### `DebateState`

The LangGraph state. Two helpers used by the metrics:

- `objections_for(argument_id)` — every challenge to one argument
- `objections_by(role)` — used by the attacker-independence metric

> **The parallel-node rule.** Both attackers write to `turns` and `objections`
> concurrently. In `GraphState` (the LangGraph `TypedDict`) those channels use
> `operator.add` reducers so appends merge. A node returning full state raises
> `InvalidUpdateError`.

---

## Persistence

### `RunMetadata`

Everything needed to reproduce a run.

| Field | Why it matters |
| --- | --- |
| `role_models` | Model ids **as resolved** — if config said `ollama/qwen3.5` and Ollama served `qwen3.5:14b-q4`, that is what is recorded |
| `temperatures`, `seed` | Sampling settings |
| `prompt_hashes` | Detects silent prompt drift — a result cannot be attributed to a prompt that has since changed |
| `corpus_version` | Which index the retrieval came from |
| `total_*_tokens` | Cost audit; three roles run on quota-limited tiers |

### `RunArtifact`

`RunMetadata` + `DebateState`, written to
`data/runs/<run_id>/artifact.json`, with `dissent.md` and `dissent.html` beside
it.

---

## Evaluation types

### `EvaluationCase`

| Field | Shown to the system? |
| --- | --- |
| `question`, `facts` | **Yes** |
| `holding`, `outcome`, `key_reasoning` | **Never** — ground truth |
| `difficulty` | No — used for breakdowns |
| `source_case_id` | No — excluded from retrieval so the answer cannot be read back |

### `Arm`

One ablation configuration: `retrieval_enabled`, `attackers`, `max_rounds`. See
`evaluation/harness/arms.py`.

---

## Keeping TypeScript in sync

`runtime/frontend/src/types/index.ts` mirrors these by hand. When a Pydantic
model changes, update it in the same PR — `make lint` type-checks the frontend
and will catch a mismatch only where the frontend actually uses the field.
