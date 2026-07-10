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
from fastapi import FastAPI, File, Form, Query, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_remote_address

from src.logging_config import setup_logging, get_request_id
from src.langfuse_tracing import init_tracing, shutdown_tracing, pipeline_span

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError("GOOGLE_API_KEY tidak ditemukan di .env")

init_tracing()

from src.graph import run_pipeline
from src.schemas import make_routing_decision, RoutingDecision, ReviewRequest
from src.database import Database
from src.metrics import get_metrics_collector

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
        log.error(
            "request_failed",
            method=request.method,
            path=request.url.path,
            error=str(exc),
        )
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

        with pipeline_span("onboarding-pipeline", account_type=account_type) as handler:
            report = run_pipeline(tmp_path, account_type, callbacks=[handler])

        if report.get("error"):
            raise ValueError(report["error"])

        extraction = report.get("extraction") or {}
        validation = report.get("validation") or {}

        log.info(
            "pipeline_completed",
            status=validation.get("status", "UNKNOWN"),
            customer_name=validation.get("customer_name", "UNKNOWN"),
        )

        decision = make_routing_decision(extraction.get("confidence", 0.0))
        result = report

        if decision == RoutingDecision.PENDING_REVIEW:
            review = ReviewRequest(
                customer_name=extraction.get("nama", "UNKNOWN"),
                confidence=extraction["confidence"],
                reason=f"Kualitas dokumen perlu diperiksa (confidence: {extraction['confidence']:.1%})",
                document_data=extraction,
            )
            result["review_request"] = review.model_dump()

        return result
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


# --- Metrics endpoints ---


@app.get("/api/v1/metrics/summary")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def metrics_summary(
    request: Request,
    hours: int | None = Query(None, ge=1, le=8760, description="Filter by last N hours"),
):
    collector = get_metrics_collector()
    summary = collector.get_summary(hours=hours)
    return JSONResponse(content=summary.model_dump())


@app.get("/api/v1/metrics/history")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def metrics_history(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Max records per page"),
    offset: int = Query(0, ge=0, description="Records to skip"),
):
    collector = get_metrics_collector()
    runs = collector.get_history(limit=limit, offset=offset)
    total = len(collector.get_all_records())
    return JSONResponse(
        content={
            "runs": [r.model_dump() for r in runs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@app.get("/api/v1/metrics/stages")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def metrics_stages(
    request: Request,
    hours: int | None = Query(None, ge=1, le=8760, description="Filter by last N hours"),
):
    collector = get_metrics_collector()
    breakdown = collector.get_stage_breakdown(hours=hours)
    return JSONResponse(content=[b.model_dump() for b in breakdown])


@app.get("/api/v1/metrics/run/{run_id}")
@limiter.limit(os.getenv("RATE_LIMIT_READ", "30/minute"))
async def metrics_run_detail(request: Request, run_id: str):
    collector = get_metrics_collector()
    all_records = collector.get_all_records()
    for record in all_records:
        if record.run_id == run_id:
            return JSONResponse(content=record.model_dump())
    raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")


# --- Dashboard ---


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    dashboard_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return HTMLResponse(content=dashboard_path.read_text(encoding="utf-8"))


# Mount static files if directory exists
_static_dir = Path(__file__).parent.parent / "dashboard"
if _static_dir.is_dir():
    app.mount("/static/dashboard", StaticFiles(directory=str(_static_dir)), name="dashboard-static")


@app.on_event("shutdown")
async def shutdown():
    shutdown_tracing()
