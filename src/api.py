"""FastAPI application for the Multi-Agent Onboarding system.

Provides REST endpoints for document validation, customer management,
and audit log retrieval.
"""

import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError("GOOGLE_API_KEY tidak ditemukan di .env")

from src.agent import extract_document_data
from src.policy_validator import validate_customer_from_document_data
from src.pii_guardian import get_pii_report, process_and_save_customer
from src.database import Database

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ACCOUNT_TYPES = {"Stocks", "ETF", "Futures", "Options", "Margin", "Forex", "Crypto"}

app = FastAPI(
    title="Multi-Agent Onboarding API",
    description="Multi-Agent document validation pipeline with PII protection",
    version="1.0.0",
)


def _run_pipeline(image_bytes: bytes, filename: str, account_type: str) -> dict:
    """
    Jalankan full pipeline validasi: extract -> validate -> PII -> save.

    Args:
        image_bytes: Raw bytes dari file gambar
        filename: Nama file asli (untuk validasi ekstensi)
        account_type: Jenis akun trading

    Returns:
        dict: Hasil pipeline dengan keys extraction, validation, pii_report, saved_record

    Raises:
        ValueError: Jika format file tidak didukung
    """
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
        document_data = extract_document_data(tmp_path)
        validation_result = validate_customer_from_document_data(
            document_data, account_type
        )
        pii_report = get_pii_report(document_data)

        record = process_and_save_customer(document_data, validation_result)

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
    """Health check endpoint."""
    return {"status": "ok", "service": "multi-agent-onboarding"}


@app.post("/api/v1/validate")
async def validate(
    file: UploadFile = File(...),
    account_type: str = Form(...),
) -> dict:
    """
    Upload dan validasi dokumen identitas nasabah.

    Menerima file gambar (KTP/Paspor) dan jenis akun, menjalankan
    pipeline 3 agent: Document Extractor -> Policy Validator -> PII Guardian.

    Args:
        file: File gambar dokumen (jpg, jpeg, png, webp)
        account_type: Jenis akun (Stocks, ETF, Futures, Options, Margin, Forex, Crypto)

    Returns:
        dict: Hasil extraction, validation, PII report, dan saved record

    Raises:
        HTTPException 400: Jika input tidak valid
        HTTPException 500: Jika pipeline error
    """
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
async def list_customers():
    """Daftar semua customer yang tersimpan."""
    db = Database()
    return JSONResponse(content=db.get_customers())


@app.get("/api/v1/audit-logs")
async def list_audit_logs():
    """Daftar semua audit log entries."""
    db = Database()
    return JSONResponse(content=db.get_audit_logs())
