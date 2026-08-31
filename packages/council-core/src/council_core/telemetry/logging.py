"""Structured logging via structlog.

Console rendering in dev (readable), JSON in prod (greppable). Every service
calls `configure_logging()` once at startup.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog and the stdlib root logger together.

    Args:
        level: Standard log level name.
        json_output: True in production so logs are machine-parseable.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Third-party libraries are chatty at INFO; they earn their place at WARNING.
    for noisy in ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
