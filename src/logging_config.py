import uuid
import structlog
import logging
from typing import Any


def setup_logging(environment: str = "development") -> None:
    """
    Configure structured logging for the application.

    In production, outputs JSON-formatted logs for ingestion by log
    aggregators (ELK, Datadog, etc.). In development, uses a human-readable
    console renderer.

    Integrates with standard logging so third-party libraries also produce
    structured output.
    """
    if environment == "production":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO if environment == "production" else logging.DEBUG)


def get_request_id() -> str:
    """Generate a unique request correlation ID."""
    return uuid.uuid4().hex[:12]
