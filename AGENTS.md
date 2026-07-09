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
```

Account types: `Stocks`, `ETF`, `Futures`, `Options`, `Margin`, `Forex`, `Crypto`

## No tests, no CI, no Docker, no API

None of these exist yet. The `PRD.md` defines P0-P2 improvements (ChromaDB, SQLite, pytest, FastAPI, Docker) — none implemented.

## Architecture

3 sequential agents, each calling Gemini 2.5 Flash via LangChain `create_agent()`:

| Agent | File | What it does |
|---|---|---|
| Document Extractor (Vision) | `src/agent.py` | Extracts ID data from images via Gemini Vision |
| Policy Validator (RAG) | `src/policy_validator.py` | Validates age/account-type via RAG + LangChain tools |
| PII Guardian (Security) | `src/pii_guardian.py` | Masks NIK/name/address before saving |

Data flow: `main.py` → agent only; `validate.py` → agent → policy → pii

## Key gotchas

- `create_agent()` from `langchain.agents`, NOT the legacy `langchain.agents.initialize`. Uses structured output via `response_format=`.
- RAG store (`src/rag_store.py`): `InMemoryVectorStore` (not persistent). On every `create_policy_validator_agent()` call, `initialize_vector_store()` re-indexes from scratch.
- Vector store is `InMemoryVectorStore` — it will be migrated to ChromaDB per PRD P0-1.
- Database (`src/pii_guardian.py:SimulatedDatabase`): JSON files at `data/db/customers.json` and `data/db/audit_log.json`. Not concurrent-safe. Per PRD P0-2, target is SQLite.
- Indonesian-language prompts and output throughout.
- `sys.stdout.reconfigure(encoding='utf-8')` in both `main.py` and `validate.py` for Windows.

## Requirements overview

```
langchain>=0.3.0, langchain-google-genai>=2.0.0, langgraph>=0.2.0
langchain-huggingface, sentence-transformers, chromadb, langchain-chroma
pydantic>=2.0.0, python-dotenv
```

FastAPI/uvicorn/multipart commented out — uncomment when implementing API.

## Config

`.env` must contain `GOOGLE_API_KEY`. `.env` is gitignored; copy from `.env.example`.