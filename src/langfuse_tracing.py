"""Langfuse tracing integration for multi-agent onboarding.

Usage:
    from src.langfuse_tracing import init_tracing, get_handler, flush_traces, pipeline_span

    init_tracing()
    handler = get_handler()

    with pipeline_span("onboarding", account_type="Futures") as span:
        result = agent.invoke({...}, config={"callbacks": [handler]})

    flush_traces()
"""

import os
from contextlib import contextmanager
from typing import Any, Optional

from langfuse import get_client
from langfuse.langchain import CallbackHandler


_HANDLER: Optional[CallbackHandler] = None


def init_tracing() -> None:
    """Initialize Langfuse client from env vars.

    Reads LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL.
    Safe to call multiple times -- Langfuse client is a singleton.
    """
    _ = get_client()
    global _HANDLER
    if _HANDLER is None:
        _HANDLER = CallbackHandler()


def get_handler() -> CallbackHandler:
    """Return the shared CallbackHandler instance."""
    if _HANDLER is None:
        raise RuntimeError("Langfuse not initialized. Call init_tracing() first.")
    return _HANDLER


def flush_traces() -> None:
    """Flush pending traces to Langfuse.

    Required before exit in short-lived (CLI) scripts.
    """
    get_client().flush()


def shutdown_tracing() -> None:
    """Shutdown Langfuse client, flushing all pending events.

    Call on API server shutdown.
    """
    get_client().shutdown()


@contextmanager
def pipeline_span(name: str, **tags: str) -> Any:
    """Context manager to group agent invocations under one trace.

    Usage:
        with pipeline_span("onboarding", account_type="Futures") as span:
            result1 = agent1.invoke({...}, config={"callbacks": [handler]})
            result2 = agent2.invoke({...}, config={"callbacks": [handler]})
    """
    from langfuse import get_client, propagate_attributes

    client = get_client()
    with client.start_as_current_observation(
        as_type="span",
        name=name,
        metadata=tags,
    ) as span:
        with propagate_attributes(metadata=tags):
            yield span
