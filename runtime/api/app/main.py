"""FastAPI application entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --port 8000

In Docker this is the container CMD; see `runtime/api/Dockerfile`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import debate, health
from council_core.telemetry import configure_logging

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging on startup and report readiness."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    log.info(
        "api_starting",
        environment=settings.environment,
        qdrant=settings.qdrant_url,
        collection=settings.qdrant_collection,
    )
    yield
    log.info("api_stopping")


app = FastAPI(
    title="United States of LLMs — Council API",
    description=(
        "Adversarial multi-agent debate for international humanitarian law analysis. "
        "Not legal advice — see DISCLAIMER.md."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(debate.router)
