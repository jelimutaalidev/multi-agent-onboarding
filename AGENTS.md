# AGENTS.md — Multi-Agent Onboarding

## Python env

```powershell
..\langchain-env\Scripts\Activate.ps1
```

## Commands

```powershell
# document extraction only
python main.py test_images/sample_ktp.png

# full pipeline (aliases -a / -s / --show-pii-report)
python validate.py test_images/sample_ktp.png -a Futures
python validate.py test_images/sample_ktp_young.png -a Futures
python validate.py test_images/sample_ktp.png -a Crypto --save --show-pii-report

# API server
python api.py
python api.py 0.0.0.0 8080

# tests
python -m pytest tests/ -v -m "not integration"
python -m pytest tests/test_api.py -v
```

Account types: `Stocks`, `ETF`, `Futures`, `Options`, `Margin`, `Forex`, `Crypto`

## Architecture

3 sequential agents, each calling Gemini 2.5 Flash via LangChain `create_agent()`:

| Agent | File | What it does |
|---|---|---|
| Document Extractor (Vision) | `src/agent.py` | Extracts ID data from images via Gemini Vision |
| Policy Validator (RAG) | `src/policy_validator.py` | Validates age/account-type via RAG + LangChain tools |
| PII Guardian (Security) | `src/pii_guardian.py` | Masks NIK/name/address before saving |

Data flow: `main.py` → agent only; `validate.py` → agent → policy → pii

### FastAPI

`src/api.py` serves 4 REST endpoints, `api.py` is the run entry point.

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/validate` | POST | Run full pipeline (file upload + account_type form) |
| `/api/v1/customers` | GET | List saved customers |
| `/api/v1/audit-logs` | GET | List audit log entries |

## Key gotchas

- `create_agent()` from `langchain.agents`, NOT the legacy `langchain.agents.initialize`. Uses structured output via `response_format=`.
- RAG store (`src/rag_store.py`): ChromaDB persistent at `data/chroma_db/`. Auto-loads on restart; pass `force_reload=True` to re-index.
- Embeddings: `HuggingFaceEndpointEmbeddings` via HF Inference API (remote, no local model). Requires `HUGGINGFACEHUB_API_TOKEN` in `.env`.
- Database (`src/database.py`): SQLite via SQLAlchemy at `data/db/onboarding.db`. Concurrent-safe (not yet production-tested).
- PII Guardian (`src/pii_guardian.py`): `mask_dict()` called *before* `Database.save_customer()`. Database receives pre-masked data.
- Indonesian-language prompts and output throughout.
- `sys.stdout.reconfigure(encoding='utf-8')` in both `main.py` and `validate.py` for Windows.
- Policy validator tests use `.func()` to unwrap `@tool` decorators (e.g., `calculate_age.func`).

## Requirements overview

```
langchain>=0.3.0, langchain-google-genai>=2.0.0, langgraph>=0.2.0
langchain-huggingface, chromadb, langchain-chroma, sqlalchemy
pydantic>=2.0.0, python-dotenv
fastapi, uvicorn, python-multipart
pytest
```

## Config

`.env` must contain `GOOGLE_API_KEY` and `HUGGINGFACEHUB_API_TOKEN`. `.env` is gitignored; copy from `.env.example`.