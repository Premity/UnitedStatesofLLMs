"""Liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.retrieval import get_retrieval_service

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness — the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, object]:
    """Readiness — dependencies are reachable.

    Reports rather than raises, so a partially-degraded stack is visible instead
    of merely down.
    """
    qdrant_ok = await get_retrieval_service().health()
    return {
        "status": "ready" if qdrant_ok else "degraded",
        "checks": {"qdrant": qdrant_ok},
    }
