# 0003 — One orchestrator service, roles as modules

**Status:** Accepted
**Date:** 2026-08-31

## Context

The system is described as a "council" of four models. That framing invites a
service-per-role architecture: a presenter container, two attacker containers, a
judge container, each with its own API.

## Decision

**One orchestrator service.** Roles are Python modules under
`runtime/api/app/roles/`, behind a common `BaseRole`. The LangGraph workflow
calls them in-process.

## Consequences

The service-per-role design would have bought nothing here:

- The debate is **sequential by nature**. The presenter must finish before the
  attackers can respond; the attackers must finish before the judge rules. The
  one genuinely parallel step — the two attackers — is `asyncio.gather` in
  practice, not a distributed workload.
- Roles share almost everything: the same domain models, the same retrieval
  results, the same citation validator, the same prompt loader. Splitting them
  means either duplicating that or publishing an internal package and versioning
  it across four deploy units.
- Four containers means four images, four health checks, four failure modes, and
  a network hop between every debate turn.

The metaphor is a reason to make the *code* legible as four roles, not a reason
to make the *deployment* four services.

**What we keep from the "council" framing:** each role owns its prompts, its
response schema, and its parsing. Turning off an attacker for an ablation arm
touches one config field. The model backend per role is a config string.

**Given up:**

- Roles cannot scale independently. Not a real constraint — throughput is bound
  by free-tier API quotas, not by our CPU.
- A crash in one role's parsing takes down the request rather than one service.
  Acceptable: a debate missing a role is not a useful result anyway.

**Revisit if:** we ever want roles running on genuinely separate hardware — for
example attackers on a GPU box and the orchestrator on a small VPS. Even then,
the `ModelConfig.api_base` indirection probably handles it without splitting the
service.
