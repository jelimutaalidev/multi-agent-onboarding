"""FastAPI application for the Multi-Agent Onboarding system.

Provides REST endpoints for document validation, customer management,
and audit log retrieval with structured logging, CORS, and rate limiting.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_remote_address

from src.logging_config import setup_logging, get_request_id
from src.langfuse_tracing import init_tracing, get_handler, flush_traces, shutdown_tracing, pipeline_span

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError("GOOGLE_API_KEY tidak ditemukan di .env")

init_tracing()
handler = get_handler()

from src.agent import extract_document_data
from src.policy_validator import validate_customer_from_document_data
from src.pii_guardian import get_pii_report, process_and_save_customer
from src.database import Database

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ACCOUNT_TYPES = {"Stocks", "ETF", "Futures", "Options", "Margin", "Forex", "Crypto"}

ENVIRONMENT = os.getenv("APP_ENV", "development")

setup_logging(ENVIRONMENT)
logger: Any = structlog.get_logger()

from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Multi-Agent Onboarding API",
    description="Multi-Agent document validation pipeline with PII protection",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

app.add_middleware(SlowAPIASGIMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> JSONResponse:
    request_id = get_request_id()
    log = logger.bind(request_id=request_id)
    log.info("request_started", method=request.method, path=request.url.path)

    try:
        response = await call_next(request)
        log.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
    except Exception as exc:
        log.error("request_failed", method=request.method, path=request.url.path, error=str(exc))
        raise

    response.headers["X-Request-ID"] = request_id
    return response


def _run_pipeline(image_bytes: bytes, filename: str, account_type: str) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Format file tidak didukung: {suffix}. "
            f"Format yang didukung: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        log = logger.bind(pipeline=True)
        log.info("pipeline_started", filename=filename, account_type=account_type)

        with pipeline_span("onboarding-pipeline", account_type=account_type):
            document_data = extract_document_data(tmp_path, callbacks=[handler])
            validation_result = validate_customer_from_document_data(
                document_data, account_type, callbacks=[handler],
            )
            pii_report = get_pii_report(document_data)
            record = process_and_save_customer(document_data, validation_result)

        log.info(
            "pipeline_completed",
            status=validation_result["status"],
            customer_name=validation_result["customer_name"],
        )

        return {
            "extraction": document_data,
            "validation": validation_result,
            "pii_report": pii_report,
            "saved_record": record,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "multi-agent-onboarding"}


@app.post("/api/v1/validate")
@limiter.limit(os.getenv("RATE_LIMIT_VALIDATE", "10/minute"))
async def validate(
    request: Request,
    file: UploadFile = File(...),
    account_type: str = Form(...),
) -> dict:
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Account type tidak valid. Pilihan: {', '.join(sorted(ACCOUNT_TYPES))}",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="File kosong")

    try:
        result = await asyncio.to_thread(
            _run_pipeline, image_bytes, file.filename or "image.jpg", account_type
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {type(e).__name__}: {e}",
        )


@app.get("/api/v1/customers")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def list_customers(request: Request):
    db = Database()
    return JSONResponse(content=db.get_customers())


@app.get("/api/v1/audit-logs")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def list_audit_logs(request: Request):
    db = Database()
    return JSONResponse(content=db.get_audit_logs())


@app.on_event("shutdown")
async def shutdown():
    shutdown_tracing()
