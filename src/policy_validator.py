"""
Policy Validator RAG Agent.

Agent ini bertugas memvalidasi apakah calon nasabah memenuhi
syarat perusahaan berdasarkan dokumen kebijakan internal.
"""

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field
from enum import Enum

from langchain.agents import create_agent
from langchain.tools import tool

from .rag_store import search_policies, initialize_vector_store


# ========== ENUMS ==========

class ValidationStatus(str, Enum):
    """Status hasil validasi"""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"


class AccountType(str, Enum):
    """Jenis akun trading yang tersedia"""
    STOCKS = "Stocks"
    ETF = "ETF"
    MUTUAL_FUNDS = "Mutual Funds"
    FUTURES = "Futures"
    OPTIONS = "Options"
    MARGIN = "Margin"
    FOREX = "Forex"
    CRYPTO = "Crypto"


# ========== SCHEMAS ==========

class ValidationRequest(BaseModel):
    """Request untuk validasi nasabah"""
    nama: str = Field(description="Nama lengkap nasabah")
    nik: str = Field(description="NIK nasabah")
    tanggal_lahir: str = Field(description="Tanggal lahir dalam format DD-MM-YYYY")
    tanggal_kadaluarsa: str = Field(description="Tanggal kadaluarsa dokumen")
    jenis_dokumen: str = Field(description="Jenis dokumen (KTP/PASPOR/SIM)")
    account_type: str = Field(description="Jenis akun yang ingin dibuka")


class ValidationResult(BaseModel):
    """Hasil validasi nasabah"""
    status: ValidationStatus = Field(description="Status validasi: APPROVED, REJECTED, atau PENDING_REVIEW")
    customer_name: str = Field(description="Nama nasabah")
    account_type: str = Field(description="Jenis akun yang diajukan")
    customer_age: int = Field(description="Usia nasabah saat ini")
    minimum_age_required: int = Field(description="Usia minimum yang dibutuhkan untuk jenis akun ini")
    reasons: list[str] = Field(description="Daftar alasan untuk keputusan validasi")
    policy_references: list[str] = Field(description="Referensi kebijakan yang relevan")
    recommendations: Optional[list[str]] = Field(default=None, description="Rekomendasi untuk nasabah jika ditolak")


# ========== TOOLS ==========

@tool
def calculate_age(birth_date: str) -> int:
    """
    Hitung usia seseorang berdasarkan tanggal lahir.
    
    Args:
        birth_date: Tanggal lahir dalam format DD-MM-YYYY
        
    Returns:
        int: Usia dalam tahun
    """
    try:
        # Parse tanggal lahir
        dob = datetime.strptime(birth_date, "%d-%m-%Y").date()
        today = date.today()
        
        # Hitung usia
        age = today.year - dob.year
        
        # Adjust jika belum ulang tahun tahun ini
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        
        return age
    except ValueError:
        return -1  # Invalid date format


@tool
def check_document_validity(expiry_date: str) -> dict:
    """
    Periksa apakah dokumen masih berlaku.
    
    Args:
        expiry_date: Tanggal kadaluarsa dalam format DD-MM-YYYY atau "SEUMUR HIDUP"
        
    Returns:
        dict: Status validitas dokumen dengan keys:
            - is_valid: bool
            - days_until_expiry: int (negatif jika sudah expired)
            - status: str
    """
    # Handle lifetime validity
    if expiry_date.upper() in ["SEUMUR HIDUP", "LIFETIME", "-"]:
        return {
            "is_valid": True,
            "days_until_expiry": 99999,
            "status": "VALID_LIFETIME"
        }
    
    try:
        exp_date = datetime.strptime(expiry_date, "%d-%m-%Y").date()
        today = date.today()
        days_diff = (exp_date - today).days
        
        if days_diff > 30:
            return {
                "is_valid": True,
                "days_until_expiry": days_diff,
                "status": "VALID"
            }
        elif days_diff > 0:
            return {
                "is_valid": True,
                "days_until_expiry": days_diff,
                "status": "EXPIRING_SOON"
            }
        elif days_diff >= -30:
            return {
                "is_valid": False,
                "days_until_expiry": days_diff,
                "status": "RECENTLY_EXPIRED"
            }
        else:
            return {
                "is_valid": False,
                "days_until_expiry": days_diff,
                "status": "EXPIRED"
            }
    except ValueError:
        return {
            "is_valid": False,
            "days_until_expiry": 0,
            "status": "INVALID_FORMAT"
        }


@tool
def search_policy_documents(query: str) -> str:
    """
    Cari informasi dalam dokumen kebijakan perusahaan.
    
    Gunakan tool ini untuk menemukan aturan dan persyaratan
    yang relevan dari EXANTE Compliance Policy.
    
    Args:
        query: Query pencarian, misalnya "usia minimum futures trading"
        
    Returns:
        str: Hasil pencarian dari dokumen kebijakan
    """
    try:
        results = search_policies(query, k=3)
        
        if not results:
            return "Tidak ditemukan informasi relevan dalam dokumen kebijakan."
        
        # Format results
        formatted = []
        for i, doc in enumerate(results, 1):
            formatted.append(f"[{i}] {doc.page_content}")
        
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Error saat mencari: {str(e)}"


@tool
def get_minimum_age_for_account(account_type: str) -> dict:
    """
    Dapatkan usia minimum yang dibutuhkan untuk jenis akun tertentu.
    
    Args:
        account_type: Jenis akun (Stocks, Futures, Options, Crypto, dll)
        
    Returns:
        dict: Informasi tentang persyaratan usia
    """
    # Mapping usia minimum berdasarkan kebijakan
    age_requirements = {
        "stocks": {"min_age": 18, "risk_level": "Low"},
        "etf": {"min_age": 18, "risk_level": "Low"},
        "mutual funds": {"min_age": 18, "risk_level": "Low"},
        "futures": {"min_age": 21, "risk_level": "High"},
        "options": {"min_age": 21, "risk_level": "High"},
        "margin": {"min_age": 21, "risk_level": "High"},
        "forex": {"min_age": 21, "risk_level": "High"},
        "crypto": {"min_age": 25, "risk_level": "Very High"},
        "cryptocurrency": {"min_age": 25, "risk_level": "Very High"},
    }
    
    account_lower = account_type.lower()
    
    if account_lower in age_requirements:
        req = age_requirements[account_lower]
        return {
            "account_type": account_type,
            "minimum_age": req["min_age"],
            "risk_level": req["risk_level"],
            "found": True
        }
    else:
        return {
            "account_type": account_type,
            "minimum_age": 18,  # Default
            "risk_level": "Unknown",
            "found": False,
            "note": "Account type not found, using default minimum age of 18"
        }


# ========== AGENT ==========

POLICY_VALIDATOR_PROMPT = """Kamu adalah Policy Validator AI untuk EXANTE, perusahaan trading dan investasi.

TUGAS UTAMA:
Memvalidasi apakah calon nasabah memenuhi syarat untuk membuka akun berdasarkan dokumen kebijakan perusahaan.

PROSES VALIDASI:
1. Gunakan tool calculate_age untuk menghitung usia nasabah dari tanggal lahir
2. Gunakan tool check_document_validity untuk memeriksa apakah dokumen masih berlaku
3. Gunakan tool get_minimum_age_for_account untuk mendapatkan usia minimum yang dibutuhkan
4. Gunakan tool search_policy_documents jika perlu informasi tambahan dari kebijakan

ATURAN VALIDASI:
- Jika usia nasabah KURANG dari usia minimum untuk jenis akun tersebut → REJECTED
- Jika dokumen sudah kadaluarsa lebih dari 30 hari → REJECTED
- Jika dokumen akan kadaluarsa dalam 30 hari → PENDING_REVIEW
- Jika semua syarat terpenuhi → APPROVED

FORMAT OUTPUT:
Berikan hasil validasi yang terstruktur dengan:
- status: APPROVED, REJECTED, atau PENDING_REVIEW
- customer_name: Nama nasabah
- account_type: Jenis akun yang diajukan
- customer_age: Usia nasabah saat ini
- minimum_age_required: Usia minimum yang dibutuhkan
- reasons: Daftar alasan untuk keputusan
- policy_references: Kutipan kebijakan yang relevan
- recommendations: Rekomendasi jika ditolak (opsional)

Selalu gunakan tools yang tersedia untuk mendapatkan informasi yang akurat."""


def create_policy_validator_agent():
    """
    Buat Policy Validator Agent dengan RAG capability.
    
    Returns:
        Agent: LangChain agent dengan tools untuk validasi
    """
    # Initialize vector store dulu
    initialize_vector_store()
    
    agent = create_agent(
        model="google_genai:gemini-2.5-flash",
        tools=[
            calculate_age,
            check_document_validity,
            search_policy_documents,
            get_minimum_age_for_account,
        ],
        system_prompt=POLICY_VALIDATOR_PROMPT,
        response_format=ValidationResult,
    )
    
    return agent


def validate_customer(
    nama: str,
    nik: str,
    tanggal_lahir: str,
    tanggal_kadaluarsa: str,
    jenis_dokumen: str,
    account_type: str
) -> dict:
    """
    Validasi calon nasabah untuk membuka akun.
    
    Args:
        nama: Nama lengkap nasabah
        nik: NIK nasabah
        tanggal_lahir: Tanggal lahir (DD-MM-YYYY)
        tanggal_kadaluarsa: Tanggal kadaluarsa dokumen
        jenis_dokumen: Jenis dokumen (KTP/PASPOR/SIM)
        account_type: Jenis akun yang ingin dibuka
        
    Returns:
        dict: Hasil validasi
    """
    from langchain.messages import HumanMessage
    
    # Create agent
    agent = create_policy_validator_agent()
    
    # Format request message
    request_text = f"""Tolong validasi calon nasabah berikut untuk pembukaan akun:

DATA NASABAH:
- Nama: {nama}
- NIK: {nik}
- Tanggal Lahir: {tanggal_lahir}
- Jenis Dokumen: {jenis_dokumen}
- Tanggal Kadaluarsa Dokumen: {tanggal_kadaluarsa}

JENIS AKUN YANG DIAJUKAN: {account_type}

Lakukan validasi lengkap dan berikan keputusan beserta alasannya."""

    message = HumanMessage(content=request_text)
    
    # Invoke agent
    result = agent.invoke({"messages": [message]})
    
    # Extract structured response
    validation_result: ValidationResult = result["structured_response"]
    
    return validation_result.model_dump()


def validate_customer_from_document_data(
    document_data: dict,
    account_type: str
) -> dict:
    """
    Validasi nasabah menggunakan data hasil ekstraksi dokumen.
    
    Args:
        document_data: Dict hasil dari extract_document_data()
        account_type: Jenis akun yang ingin dibuka
        
    Returns:
        dict: Hasil validasi
    """
    return validate_customer(
        nama=document_data.get("nama", ""),
        nik=document_data.get("nik", ""),
        tanggal_lahir=document_data.get("tanggal_lahir", ""),
        tanggal_kadaluarsa=document_data.get("tanggal_kadaluarsa", ""),
        jenis_dokumen=document_data.get("jenis_dokumen", ""),
        account_type=account_type
    )
