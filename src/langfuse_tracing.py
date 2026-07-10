"""Langfuse tracing integration for multi-agent onboarding.

Usage:
    from src.langfuse_tracing import init_tracing, get_handler, flush_traces, pipeline_span

    init_tracing()

    # Multi-agent pipeline (grouped under one trace):
    with pipeline_span("onboarding", account_type="Futures") as handler:
        result = agent.invoke({...}, config={"callbacks": [handler]})

    # Single-agent script (creates its own trace):
    handler = get_handler()
    result = agent.invoke({...}, config={"callbacks": [handler]})

    flush_traces()
"""

import logging
import os
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

logger = logging.getLogger(__name__)

# Keep a reference so init_tracing() can be called multiple times safely
_client_initialized = False


def init_tracing() -> None:
    """Initialize Langfuse client from env vars.

    Reads LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASE_URL.
    Configures a configurable timeout for trace export.
    Safe to call multiple times -- Langfuse client is a singleton.
    """
    global _client_initialized
    if _client_initialized:
        return
    _client_initialized = True

    timeout = int(os.getenv("LANGFUSE_TIMEOUT", "10"))
    Langfuse(
        timeout=timeout,
    )


def get_handler() -> CallbackHandler:
    """Create a new CallbackHandler.

    If called inside a pipeline_span() context, the handler automatically
    nests its observations under the parent span.
    If called at module level (no active context), each agent.invoke()
    creates its own top-level trace.
    """
    return CallbackHandler()


def flush_traces() -> None:
    """Flush pending traces to Langfuse.

    Required before exit in short-lived (CLI) scripts.
    Non-blocking: logs warning if flush fails (network issues).
    """
    try:
        get_client().flush()
    except Exception:
        pass


def shutdown_tracing() -> None:
    """Shutdown Langfuse client, flushing all pending events.

    Call on API server shutdown.
    Non-blocking: logs warning if shutdown fails (network issues).
    """
    try:
        get_client().shutdown()
    except Exception:
        pass


@contextmanager
def pipeline_span(name: str, **tags: str) -> Any:
    """Context manager to group agent invocations under one trace.

    Creates a parent span AND a CallbackHandler inside that span context,
    so all agent calls using the yielded handler nest under the pipeline trace.

    Usage:
        with pipeline_span("onboarding", account_type="Futures") as handler:
            result1 = agent1.invoke({...}, config={"callbacks": [handler]})
            result2 = agent2.invoke({...}, config={"callbacks": [handler]})
    """
    from langfuse import get_client

    client = get_client()
    with client.start_as_current_observation(
        as_type="span",
        name=name,
        metadata=tags,
    ):
        handler = CallbackHandler()
        yield handler
