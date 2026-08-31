# 0002 — LiteLLM as the single model gateway

**Status:** Accepted
**Date:** 2026-08-31

## Context

Four roles run on four backends: Mistral API (presenter), Ollama ×2 (attackers),
Google AI Studio (judge). The project brief also requires that the attacker
backend be switchable to Cloudflare Workers AI for hosted demonstration, since
a demo machine may not have a GPU.

Using each provider's own SDK means four client libraries, four auth mechanisms,
four error taxonomies, four retry implementations — and a *code change* every
time a backend moves.

## Decision

Route every model call through **LiteLLM's Python SDK**. A role's backend is a
config string in the LiteLLM `<provider>/<model>` format, read from environment.

Use the SDK directly, not the LiteLLM proxy server. The proxy would add a
container and a network hop for routing we do in-process anyway.

`council_core.llm.CouncilLLM` wraps it with the three things the debate needs on
top: structured-output parsing with a repair retry, token accounting for run
artifacts, and logging keyed by role rather than raw model id.

## Consequences

**Gained:**

- Switching attackers from Ollama to Cloudflare is an env-var change:
  `COUNCIL_ATTACKER_DOCTRINAL_MODEL=cloudflare/@cf/qwen/...`
- One retry, timeout, and error-handling path for every backend
- Per-call token counts for free, which matters because three of the four roles
  run on quota-limited free tiers
- Ablation arms can vary models without touching code

**Given up:**

- A dependency that moves fast and occasionally breaks on minor releases —
  pinned with a lower bound, and worth watching
- **Size.** LiteLLM is 110MB installed and pulls in `botocore`, `openai`, and
  `grpc` as provider SDKs regardless of which providers we actually use. It is
  the single largest dependency in the API image — larger than the ONNX
  embedding runtime it sits beside. Acceptable for four backends behind one
  interface, but it is the first thing to look at if image size ever matters.
- Provider-specific features are reachable only through LiteLLM's passthrough
- One more abstraction layer to debug through when a call misbehaves

**Note:** LiteLLM normalises the *call*, not the *behaviour*. A 12B local model
and Gemini 2.5 Pro respond very differently to the same prompt — particularly on
structured output, which is why `complete_structured` has a repair path. Small
local models routinely wrap JSON in prose.
