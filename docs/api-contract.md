# API contract

Base URL in dev: `http://localhost:8000`. The frontend reaches it through `/api`
(the Vite proxy in dev, nginx in prod, both stripping the prefix).

Interactive docs at `/docs`.

---

## Health

### `GET /health`

Liveness. Always `200` while the process is up.

```json
{ "status": "ok" }
```

### `GET /health/ready`

Readiness. Reports rather than raises, so a partially degraded stack is visible
instead of merely down.

```json
{ "status": "ready", "checks": { "qdrant": true } }
```

`status` is `"degraded"` when any check fails.

---

## Debate

### `POST /debate/stream`

Runs a debate and streams turn-level events. Returns `text/event-stream`.

**Request:**

```json
{
  "question": "Does the strike constitute a war crime under Article 8(2)(b)(iv)?",
  "facts": "On 12 March, aircraft struck a facility…",
  "rounds": "auto",
  "max_rounds": 3,
  "enabled_attackers": ["attacker_doctrinal", "attacker_evidentiary"],
  "retrieval_enabled": true,
  "top_k": 8
}
```

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `question` | string | required | The legal question |
| `facts` | string | `""` | Factual predicate |
| `rounds` | int \| `"auto"` | `"auto"` | `auto` lets the judge terminate early |
| `max_rounds` | int 1–5 | `3` | Hard ceiling in every mode |
| `enabled_attackers` | Role[] | both | Empty = single-pass (ablation arms A/B) |
| `retrieval_enabled` | bool | `true` | False = ungrounded (arm A) |
| `top_k` | int 1–50 | `8` | Corpus spans retrieved |

**Events:**

| Event | Payload | When |
| --- | --- | --- |
| `start` | `{"run_id": "run_a1b2c3d4e5f6"}` | Immediately |
| `turn` | Full `Turn` object | Each role completes |
| `verdict` | `Verdict` object | The judge rules (once per round) |
| `error` | `{"error": "..."}` | The run fails |
| `done` | `{"run_id": "...", "status": "completed"}` | Stream ends |

Turn-level, not token-level: a four-model debate runs for minutes, and turn
boundaries are what the courtroom animates against.

**Client note:** this is a POST, so `EventSource` cannot be used — it issues GETs
only. Read the response body as a stream and parse frames manually; see
`runtime/frontend/src/hooks/useDebateStream.ts`.

**Concurrency:** bounded by `MAX_CONCURRENT_DEBATES` (default 2). Requests
beyond that wait rather than failing — three of four roles run on free-tier
quotas.

**The run is always persisted**, including on failure, so a failed debate can
still be inspected.

---

### `GET /debate/runs?limit=50`

Recent runs, newest first. Returns `RunMetadata[]` — metadata only, not full
artifacts.

### `GET /debate/runs/{run_id}`

One complete `RunArtifact`: metadata plus the full `DebateState` — every turn,
argument, objection, resolved citation, and the verdict.

`404` if not found.

### `GET /debate/runs/{run_id}/export.md`

The dissent log as Markdown, `Content-Disposition: attachment`.

### `GET /debate/runs/{run_id}/export.html`

Print-ready HTML — self-contained, open and print to PDF.

---

## Types

Authoritative definitions in `packages/council-core/src/council_core/models/`.
The TypeScript mirror is `runtime/frontend/src/types/index.ts` and **must be
kept in sync by hand**.

### Role

`presenter` · `attacker_doctrinal` · `attacker_evidentiary` · `judge` · `retriever`

### CitationStatus

| Value | Meaning |
| --- | --- |
| `resolved` | Locator exists; text attached |
| `unresolved` | Instrument indexed, locator missing — **fabrication signal** |
| `out_of_corpus` | Real authority, not indexed — unverifiable |
| `misquoted` | Locator resolves, quoted text does not match |

### ObjectionDisposition

`sustained` · `overruled` · `partial` · `unaddressed`

`overruled` objections become the dissent log.

### Turn

```json
{
  "id": "turn_a1b2c3d4",
  "round_number": 1,
  "role": "attacker_doctrinal",
  "model_id": "ollama/qwen3.5:14b",
  "prompt_id": "attacker_doctrinal/challenge",
  "prompt_hash": "sha256…",
  "arguments": [],
  "objections": [ /* Objection[] */ ],
  "raw_response": "…",
  "started_at": "2026-08-31T12:00:00Z",
  "completed_at": "2026-08-31T12:00:42Z",
  "prompt_tokens": 3200,
  "completion_tokens": 850,
  "error": null
}
```

### Verdict

```json
{
  "conclusion": "The attack was disproportionate.",
  "reasoning": "…",
  "confidence": 0.62,
  "confidence_reasoning": "The proportionality assessment is genuinely contested…",
  "surviving_argument_ids": ["arg_1", "arg_3"],
  "dissent": [ /* overruled Objection[] */ ]
}
```

---

## Errors

| Status | When |
| --- | --- |
| `404` | Run not found |
| `422` | Request body failed validation |
| `500` | Unhandled server error |

Failures during a stream arrive as an `error` **event**, not an HTTP status —
headers are already sent by then.
