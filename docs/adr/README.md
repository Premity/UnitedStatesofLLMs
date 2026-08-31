# Architecture Decision Records

Short records of decisions that had real trade-offs, written when the decision
was made rather than reconstructed later.

The point is not ceremony. It is that in three weeks someone — quite possibly
the person who made the decision — will ask "why don't we just use Postgres for
this?", and the answer should take thirty seconds to find rather than an hour to
re-derive.

## Format

```markdown
# NNNN — Title

**Status:** Accepted | Superseded by NNNN
**Date:** YYYY-MM-DD

## Context
What was the situation, and what forced a choice?

## Decision
What we chose.

## Consequences
What this costs us, and what would make us revisit it.
```

Keep them short. A page is plenty.

## Index

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-no-torch-fastembed.md) | Embeddings via fastembed/ONNX, no PyTorch | Accepted |
| [0002](0002-litellm-model-gateway.md) | LiteLLM as the single model gateway | Accepted |
| [0003](0003-single-orchestrator-service.md) | One orchestrator service, roles as modules | Accepted |
| [0004](0004-citation-integrity.md) | Citation validation as first-class machinery | Accepted |
| [0005](0005-json-run-artifacts.md) | Run artifacts as JSON files, not a database | Accepted |
| [0006](0006-ollama-host-by-default.md) | Ollama on the host by default, compose profile optional | Accepted |
| [0007](0007-curated-corpus.md) | Curated corpus scoped by manifest, not a crawl | Accepted |
