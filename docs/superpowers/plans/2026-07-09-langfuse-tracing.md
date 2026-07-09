# Langfuse Tracing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Langfuse observability tracing to all 3 agents, with 1 trace per pipeline session and proper flush handling.

**Architecture:** Shared `src/langfuse_tracing.py` module exports `init_tracing()` + `get_handler()` + `flush_traces()`. Each entry point calls `init_tracing()`. Each agent invoke passes `config={"callbacks": [handler]}`. CLI scripts call `flush_traces()` before exit. Pipeline agents grouped under 1 trace via `start_as_current_observation`.

**Tech Stack:** langfuse>=4.0.0 (Python SDK), LangChain CallbackHandler, env-driven config

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/langfuse_tracing.py` | **Create** | Init Langfuse client, export `get_handler()`, `flush_traces()`, `shutdown_tracing()`, `pipeline_span()` context manager |
| `requirements.txt` | **Modify** | Add `langfuse>=4.0.0` |
| `.env.example` | **Modify** | Replace LangSmith vars with LANGFUSE_ vars |
| `src/agent.py` | **Modify** | Accept optional callbacks param in invoke functions |
| `src/policy_validator.py` | **Modify** | Accept optional callbacks param in invoke functions |
| `src/pii_guardian.py` | **Modify** | Accept optional callbacks param in `process_and_save_customer` |
| `validate.py` | **Modify** | Call `init_tracing()` early, wrap pipeline in `pipeline_span()`, `flush_traces()` at end |
| `main.py` | **Modify** | Call `init_tracing()` early, `flush_traces()` at end |
| `src/api.py` | **Modify** | Call `init_tracing()` early, wrap pipeline in `pipeline_span()`, shutdown on app shutdown |
| `AGENTS.md` | **Modify** | Add Langfuse setup instructions |

### Task 1: Create `src/langfuse_tracing.py`

**Files:**
- Create: `src/langfuse_tracing.py`

- [ ] **Step 1: Write file**

```python
"""Langfuse tracing integration for multi-agent onboarding.

Usage:
    from src.langfuse_tracing import init_tracing, get_handler, flush_traces, pipeline_span

    init_tracing()  # call once at startup
    handler = get_handler()

    with pipeline_span("onboarding", account_type="Futures") as span:
        result = agent.invoke({...}, config={"callbacks": [handler]})

    flush_traces()  # call before exit in CLI scripts
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
    Safe to call multiple times — Langfuse client is a singleton.
    """
    _ = get_client()  # ensures singleton is created from env
    global _HANDLER
    if _HANDLER is None:
        _HANDLER = CallbackHandler()


def get_handler() -> CallbackHandler:
    """Return the shared CallbackHandler instance."""
    if _HANDLER is None:
        raise RuntimeError(
            "Langfuse not initialized. Call init_tracing() first."
        )
    return _HANDLER


def flush_traces() -> None:
    """Flush pending traces to Langfuse.

    Required before exit in short-lived (CLI) scripts.
    Safe to call from long-lived (API) apps but unnecessary.
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
    from langfuse import get_client
    from langfuse.langchain import propagate_attributes

    client = get_client()
    with client.start_as_current_observation(
        as_type="span",
        name=name,
        metadata=tags,
    ) as span:
        with propagate_attributes(**tags):
            yield span
```

- [ ] **Step 2: Verify file parses**

Run: `python -c "import ast; ast.parse(open('src/langfuse_tracing.py').read()); print('OK')"`
Expected: OK

### Task 2: Add dep + update env template

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add langfuse to requirements.txt**

```python
# LLM Observability
langfuse>=4.0.0
```

- [ ] **Step 2: Replace LangSmith with Langfuse in .env.example**

```
# Langfuse (LLM Observability)
# Get keys from https://cloud.langfuse.com (free tier: 50K traces/month)
# LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

- [ ] **Step 3: Install dependency**

Run: `pip install langfuse>=4.0.0`
Expected: Installed successfully

### Task 3: Modify `src/agent.py` to accept callbacks

**Files:**
- Modify: `src/agent.py`

- [ ] **Step 1: Add `callbacks` parameter to `extract_document_data` and `extract_document_data_from_base64`**

Both functions already exist. Change signature to accept optional callbacks and pass them via `config`.

```python
def extract_document_data(image_path: Union[str, Path], callbacks: Optional[list] = None) -> dict:
    # ... same body ...
    result = agent.invoke(
        {"messages": [message]},
        config={"callbacks": callbacks or []},
    )
```

Same for `extract_document_data_from_base64`.

### Task 4: Modify `src/policy_validator.py` to accept callbacks

**Files:**
- Modify: `src/policy_validator.py`

- [ ] **Step 1: Add `callbacks` parameter to `validate_customer`**

```python
def validate_customer(..., callbacks: Optional[list] = None) -> dict:
    # ... same body ...
    result = agent.invoke(
        {"messages": [message]},
        config={"callbacks": callbacks or []},
    )
```

- [ ] **Step 2: Pass through `callbacks` in `validate_customer_from_document_data`**

```python
def validate_customer_from_document_data(document_data: dict, account_type: str, callbacks: Optional[list] = None) -> dict:
    return validate_customer(..., callbacks=callbacks)
```

### Task 5: Modify `src/pii_guardian.py` to accept callbacks

**Files:**
- Modify: `src/pii_guardian.py`

- [ ] **Step 1: Add `callbacks` parameter to `create_pii_guardian` agent invoke**

In `create_pii_guardian()`, the agent is invoked when `save_to_secure_database` tool is called. But actually, the PII Guardian agent is invoked from `validate.py` where `process_and_save_customer` and `get_pii_report` are called directly — the agent itself is less used.

The key point: `process_and_save_customer` accepts callbacks. The agent creation function (`create_pii_guardian`) also needs to pass callbacks.

Actually, looking at the code flow:
1. `validate.py` calls `get_pii_report(document_data)` — this is `src/pii_guardian.py` — it just calls `mask_dict()` directly (no agent invoke)
2. `validate.py` calls `process_and_save_customer(document_data, validation_result)` — this calls `mask_dict()` then `db.save_customer()` — again no agent invoke

The actual PII Guardian agent (`create_pii_guardian()`) is invoked separately. So the direct function calls don't need callback passing. We only need to handle the `create_pii_guardian()` agent if it's ever invoked.

Actually looking more carefully at `validate.py`, it DOES NOT invoke `create_pii_guardian()` — it directly uses `mask_dict()` and `get_pii_report()` and `process_and_save_customer()`. So there's no PII agent invoke to trace.

BUT — we should still make sure that if someone uses the agent, it can accept callbacks. Let me add the parameter to `create_pii_guardian()` and its tool functions.

Actually, for simplicity and YAGNI: the Agent function `create_pii_guardian()` creates an agent but doesn't invoke it — the caller does. Since no one currently calls the agent (they use direct functions), let me skip this for now.

But wait — let me re-read `api.py`. In `_run_pipeline`:
```python
document_data = extract_document_data(tmp_path)
validation_result = validate_customer_from_document_data(document_data, account_type)
pii_report = get_pii_report(document_data)
record = process_and_save_customer(document_data, validation_result)
```

No PII agent invoke. So the only agent invokes we need to trace are:
1. `extract_document_data` → `agent.invoke` in `agent.py`
2. `validate_customer_from_document_data` → `validate_customer` → `agent.invoke` in `policy_validator.py`

No changes needed to `pii_guardian.py` for callbacks. Clean.

### Task 6: Update `validate.py` to initialize + wrap tracing

**Files:**
- Modify: `validate.py`

- [ ] **Step 1: Add init_tracing, wrap pipeline in pipeline_span(), flush at end**

```python
from src.langfuse_tracing import init_tracing, get_handler, flush_traces, pipeline_span

# After load_dotenv():
init_tracing()
handler = get_handler()

# Wrap the pipeline in a pipeline_span:
with pipeline_span("onboarding-pipeline", account_type=args.account_type):
    document_data = extract_document_data(args.image_path, callbacks=[handler])
    validation_result = validate_customer_from_document_data(
        document_data, args.account_type, callbacks=[handler]
    )
    pii_report = get_pii_report(document_data)
    if args.save:
        record = process_and_save_customer(document_data, validation_result)

# At the very end before sys.exit:
flush_traces()
```

### Task 7: Update `src/api.py` to initialize + wrap tracing

**Files:**
- Modify: `src/api.py`

- [ ] **Step 1: Add init_tracing after load_dotenv**

```python
from src.langfuse_tracing import init_tracing, get_handler, flush_traces, pipeline_span

# After load_dotenv():
init_tracing()
handler = get_handler()
```

- [ ] **Step 2: Wrap `_run_pipeline` in pipeline_span**

```python
def _run_pipeline(image_bytes: bytes, filename: str, account_type: str) -> dict:
    ...
    with pipeline_span("onboarding-pipeline", account_type=account_type) as span:
        document_data = extract_document_data(tmp_path, callbacks=[handler])
        validation_result = validate_customer_from_document_data(
            document_data, account_type, callbacks=[handler]
        )
        pii_report = get_pii_report(document_data)
        record = process_and_save_customer(document_data, validation_result)
    ...
```

- [ ] **Step 3: Add shutdown on app shutdown event**

```python
@app.on_event("shutdown")
async def shutdown():
    shutdown_tracing()
```

### Task 8: Update `main.py` to initialize + flush tracing

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add init_tracing, flush**

```python
from src.langfuse_tracing import init_tracing, get_handler, flush_traces

# After load_dotenv():
init_tracing()
handler = get_handler()

# Modify extract_document_data call to pass callbacks:
result = extract_document_data(image_path, callbacks=[handler])

# Before sys.exit:
flush_traces()
```

### Task 9: Run tests to verify nothing broken

- [ ] **Step 1: Run unit tests**

Run: `python -m pytest tests/ -v -m "not integration"`
Expected: All tests pass

### Task 10: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add Langfuse section**

```markdown
## Langfuse Tracing

LLM observability via Langfuse Cloud (free tier: 50K traces/month).

| Env Var | Description |
|---|---|
| `LANGFUSE_SECRET_KEY` | Secret key from cloud.langfuse.com |
| `LANGFUSE_PUBLIC_KEY` | Public key from cloud.langfuse.com |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` (or self-hosted URL) |

Data flow: `init_tracing()` at entry point → `CallbackHandler` passed as `config` to each `agent.invoke()` → pipeline steps grouped under one trace via `pipeline_span()` context manager → `flush_traces()` before CLI exit.

Agents produce 3 separate spans under 1 trace per pipeline session.
```
