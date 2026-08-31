# syntax=docker/dockerfile:1
#
# The orchestrator service. Inherits council-core from council-base.
# Build the base first: `make build-base`.

FROM council-base AS deps

WORKDIR /app

# Dependencies install in their own layer so a code change does not reinstall them.
COPY runtime/api/pyproject.toml /app/runtime/api/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        "langgraph>=0.2.45" \
        "qdrant-client>=1.12" \
        "fastembed>=0.4.2" \
        "sse-starlette>=2.1" \
        "httpx>=0.27"

# ── Runtime image ────────────────────────────────────────────────────────────
FROM deps AS runtime

WORKDIR /app

COPY runtime/api/app /app/app
COPY prompts /app/prompts

# Run as a non-root user.
RUN useradd --create-home --uid 1000 council \
    && chown -R council:council /app
USER council

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
