# 0001 — Embeddings via fastembed/ONNX, no PyTorch

**Status:** Accepted
**Date:** 2026-08-31

## Context

The system needs BGE-M3 embeddings for retrieval over the IHL corpus. The
obvious route is `sentence-transformers`, which pulls in PyTorch.

That has a real cost. A prior project in this codebase family
(RE-Lore Oracle) needed a shared base image, a `TORCH_DEVICE` build argument
with GPU auto-detection, CPU and CUDA wheel variants, and GHCR publishing —
all of it existing purely to stop every service downloading 2.5GB of CUDA
independently. Builds took tens of minutes and the base image had to be built
before anything else would work at all.

The question was whether we need any of that.

We do not. The only ML workload in this repo is embedding text. There is no
reranker, no image model, no fine-tuning. Every generative model runs behind an
API or Ollama, both of which are HTTP calls.

## Decision

Use **fastembed**, which runs BGE-M3 through the ONNX runtime. No PyTorch
anywhere in the repository.

The shared base image (`Dockerfile.base`) is kept, but it now holds the pinned
Python runtime, `uv`, and the `council-core` package rather than gigabytes of ML
dependencies.

## Consequences

**Gained:**

- The ONNX runtime that replaces torch is 66MB, against ~2.5GB for
  PyTorch + CUDA. Measured in the built image, not estimated.
- Builds finish in about a minute rather than tens of minutes
- No `TORCH_DEVICE` argument, no GPU detection, no CPU/CUDA wheel split
- No need to publish pre-built images to GHCR so teammates can skip slow builds
- CI `docker build` is fast enough to run on every PR

**Given up:**

- No GPU acceleration for embedding. Irrelevant at our corpus size — indexing is
  a one-off offline job over tens of thousands of spans.
- Less control over pooling and normalisation than `sentence-transformers`
  exposes. We do not currently need it.
- Adding a cross-encoder reranker later would need either an ONNX reranker
  (fastembed supports these) or reintroducing torch.

**Revisit if:** we add a reranker with no ONNX build available, or the corpus
grows by two orders of magnitude and indexing time becomes a bottleneck.

**What this decision does *not* buy us.** The API image is ~924MB, and the
embedding stack is a minority of that. The largest single dependency is LiteLLM
at 110MB, which pulls in `botocore`, `openai`, and `grpc` as provider SDKs even
though we use four providers and not the fifty it supports. Avoiding torch kept
roughly 2.4GB out of the image; it did not produce a small image. If image size
becomes a problem, LiteLLM's transitive provider SDKs are the place to look,
not the embedder — see [ADR 0002](0002-litellm-model-gateway.md).

**Constraint this creates:** the embedding model must be identical in the
indexer and the API. A collection built with one model and queried with another
returns meaningless similarity scores, silently. `EMBEDDING_MODEL` is therefore
set in one place and read by both.
