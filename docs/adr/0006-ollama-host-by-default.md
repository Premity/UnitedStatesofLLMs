# 0006 — Ollama on the host by default, compose profile optional

**Status:** Accepted
**Date:** 2026-08-31

## Context

The two attackers run on locally hosted models via Ollama. There were three ways
to wire this:

1. Ollama as a compose service with a named volume for weights
2. Ollama on the host, containers reaching it via `host.docker.internal`
3. Both — host by default, containerised behind an optional profile

The deciding factor is that this is a four-person team with four different
machines, and at least one of them will not have a usable GPU.

## Decision

**Host Ollama by default**, with an optional `ollama` compose profile.

`COUNCIL_OLLAMA_BASE_URL` controls it and defaults to
`http://host.docker.internal:11434`. The API container declares
`extra_hosts: host.docker.internal:host-gateway`, which is required on Linux
(Docker Desktop provides it automatically).

To run it containerised instead:

```bash
docker compose --profile ollama up -d
# and set COUNCIL_OLLAMA_BASE_URL=http://ollama:11434
```

## Consequences

**Gained:**

- Teammates who already run Ollama share one model store across all their work
  rather than re-pulling ~20GB into a Docker volume
- No GPU passthrough configuration in the default path — that is where this
  usually goes wrong on Linux
- A wiped Docker volume does not cost a 20GB re-download
- The containerised path still exists for anyone who wants one-command setup

**Given up:**

- The default stack is not fully self-contained. `make setup` checks for Ollama
  and tells the user what to install.
- Two supported configurations to keep working, though the difference is a
  single URL.

**Note:** the same indirection covers the hosted-demo case. Pointing the
attackers at Cloudflare Workers AI is a model-id change, and `api_base` is only
injected for `ollama/`-prefixed models — see
[ADR 0002](0002-litellm-model-gateway.md).
