# AGENTS.md — Multi-Agent Onboarding

## Python env
```powershell
..\langchain-env\Scripts\Activate.ps1
```

## Commands

```powershell
# document extraction only
python main.py test_images/sample_ktp.png

# full pipeline
python validate.py test_images/sample_ktp.png -a Futures
python validate.py test_images/sample_ktp_young.png -a Futures
python validate.py test_images/sample_ktp.png -a Crypto --save --show-pii-report

# API server
python api.py
python api.py 0.0.0.0 8080

# Make targets (mirrors CI order)
make install
make lint           # ruff check src/ tests/
make typecheck      # mypy src/ (soft-fail in CI)
make test           # pytest -m "not integration" --tb=short
make format         # ruff format src/ tests/
make api            # python api.py 0.0.0.0 8000
make docker-up

# single file
python -m pytest tests/test_api.py -v
python -m pytest tests/test_policy_validator.py -v
python -m pytest tests/test_graph.py -v
```

Account types (CLI `-a` / `--account-type`): `Stocks`, `ETF`, `Futures`, `Options`, `Margin`, `Forex`, `Crypto`

> Note: `Mutual Funds` exists in the `AccountType` enum in `policy_validator.py` but is NOT wired into `validate.py` CLI or `src/api.py` API validation.

## Architecture

LangGraph `StateGraph` pipeline orchestrated via `src/graph.py`. Nodes are wrapped as LangGraph nodes; the graph handles sequential execution, conditional routing, and tracing automatically.

```
START → extract_document → [confidence ≥ 0.7?] → validate_policy → mask_pii → save_customer → generate_report → END
                              ↓ (rejected)
                          generate_report → END
```

| Node | Type | File | Model | Tools |
|---|---|---|---|---|
| `extract_document` | LLM Agent | `src/agent.py` | `gemini-2.5-flash-lite` | — (Vision-only) |
| `validate_policy` | LLM Agent | `src/policy_validator.py` | `gemini-3.1-flash-lite` | `calculate_age`, `check_document_validity`, `search_policy_documents`, `get_minimum_age_for_account` |
| `mask_pii` | Pure function | `src/pii_guardian.py` | — (no LLM) | — |
| `save_customer` | Pure function | `src/pii_guardian.py` | — (no LLM) | — |

PII Guardian is **not an agent** — `mask_dict()` is a deterministic pure function called directly from the graph node. The `create_pii_guardian()` agent factory was removed (dead code — tools were never invoked in the pipeline).

Entry points use `run_pipeline(image_path, account_type, callbacks)` from `src/graph.py`. The graph uses a `ContextVar` to pass Langfuse callbacks through nodes without contaminating serializable state.

### FastAPI

`src/api.py` is the FastAPI app. `api.py` is the CLI entry point (uvicorn runner).
Docker CMD: `uvicorn src.api:app --host 0.0.0.0 --port 8000` (NOT `api.py`, no `--reload`).

API file upload only accepts extensions: `.jpg`, `.jpeg`, `.png`, `.webp` (GIF/BMP accepted by agent.py but blocked at API level).

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/validate` | POST | File upload + account_type form → pipeline |
| `/api/v1/customers` | GET | List saved customers |
| `/api/v1/audit-logs` | GET | List audit log entries |

API features: `structlog` (JSON in prod, human-readable in dev), `slowapi` rate limiting (configurable via `RATE_LIMIT_VALIDATE`/`RATE_LIMIT_READ` in `.env`), CORS (origins from `CORS_ORIGINS`).

## Key gotchas

- `create_agent()` from `langchain.agents`, NOT the legacy `langchain.agents.initialize`. Uses structured output via `response_format=` (Pydantic schema).
- RAG store (`src/rag_store.py`): ChromaDB persistent at `data/chroma_db/`. Auto-loads from disk on restart; pass `force_reload=True` to re-index from scratch.
- Embeddings: `HuggingFaceEndpointEmbeddings` via HF Inference API (remote, no local model). Requires `HUGGINGFACEHUB_API_TOKEN` in `.env`.
- Database (`src/database.py`): SQLite via SQLAlchemy at `data/db/onboarding.db`. `Database()` creates tables on init if missing. Not yet production-tested for concurrency.
- PII Guardian (`src/pii_guardian.py`): `mask_dict()` is a pure function called from the LangGraph `mask_pii` node, *before* `Database.save_customer()`. Database receives pre-masked data. `create_pii_guardian()` was removed — it was dead code (its tools were never invoked in the pipeline).
- Indonesian-language prompts and output throughout.
- `sys.stdout.reconfigure(encoding='utf-8')` in `main.py`, `validate.py`, AND `api.py` (entry points only).
- Policy validator tests use `.func()` to unwrap `@tool` decorators (e.g., `calculate_age.func`).
- Pre-commit hooks: `ruff --fix` + `ruff-format`. CI runs `ruff check` → `mypy` (soft-fail) → `pytest`.
- `test_rag_store.py` has `@pytest.mark.integration` tests that need live HF Embeddings API. Default `make test` excludes them via `-m "not integration"`.

## Langfuse Tracing

`init_tracing()` → `with pipeline_span(name, **tags) as handler:` wraps multi-agent pipeline → `handler` created inside span context so all `agent.invoke(config={"callbacks": [handler]})` calls nest under one trace → `flush_traces()` before CLI exit. For single-agent scripts, `get_handler()` returns a fresh handler (creates its own trace). On API server, `shutdown_tracing()` on app shutdown.

Inside LangGraph nodes, callbacks flow through a `ContextVar` (`_callbacks_var`) set by `run_pipeline()` before `graph.invoke()`. Pure function nodes (`mask_pii`, `save_customer`) don't consume LLM callbacks but still appear in LangSmith traces via LangGraph's native `RunnableLambda` wrapping.

| Env Var | Description |
|---|---|
| `LANGFUSE_SECRET_KEY` | Secret key from cloud.langfuse.com |
| `LANGFUSE_PUBLIC_KEY` | Public key from cloud.langfuse.com |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` (or self-hosted) |

All optional — tracing is a no-op when env vars are absent.

## Config

`.env` must contain `GOOGLE_API_KEY` and `HUGGINGFACEHUB_API_TOKEN`. Optional: `APP_ENV`, `CORS_ORIGINS`, `RATE_LIMIT_VALIDATE`, `RATE_LIMIT_READ`, `LANGFUSE_*`. Copy from `.env.example`.
