"""
Pydantic schemas untuk structured output dari Document Extractor Agent.
"""

from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field


class RoutingDecision(str, Enum):
    """Keputusan routing berdasarkan confidence score hasil ekstraksi dokumen."""

    PROCEED = "PROCEED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REJECTED = "REJECTED"


CONFIDENCE_THRESHOLDS: dict[RoutingDecision, float] = {
    RoutingDecision.PROCEED: 0.7,
    RoutingDecision.PENDING_REVIEW: 0.3,
    RoutingDecision.REJECTED: 0.0,
}


def make_routing_decision(confidence: float) -> RoutingDecision:
    """
    Klasifikasikan confidence score ke dalam RoutingDecision.

    Args:
        confidence: Nilai keyakinan ekstraksi (0.0 - 1.0).

    Returns:
        RoutingDecision berdasarkan threshold:
        - >= 0.7 → PROCEED
        - >= 0.3 → PENDING_REVIEW
        - < 0.3 → REJECTED
    """
    if confidence >= CONFIDENCE_THRESHOLDS[RoutingDecision.PROCEED]:
        return RoutingDecision.PROCEED
    if confidence >= CONFIDENCE_THRESHOLDS[RoutingDecision.PENDING_REVIEW]:
        return RoutingDecision.PENDING_REVIEW
    return RoutingDecision.REJECTED


class DocumentType(str, Enum):
    """Jenis dokumen identitas yang didukung"""

    KTP = "KTP"
    PASPOR = "PASPOR"
    SIM = "SIM"
    UNKNOWN = "UNKNOWN"


class DocumentData(BaseModel):
    """
    Schema untuk data yang diekstrak dari KTP/Paspor/SIM.

    Digunakan sebagai response_format pada create_agent
    untuk mendapatkan structured output.
    """

    nama: str = Field(
        description="Nama lengkap sesuai dokumen. Jika tidak terbaca, isi 'TIDAK TERBACA'"
    )

    nik: str = Field(
        description="Nomor Induk Kependudukan (16 digit untuk KTP). Jika tidak terbaca atau format salah, isi 'TIDAK TERBACA'"
    )

    tanggal_lahir: str = Field(
        description="Tanggal lahir dalam format DD-MM-YYYY. Jika tidak terbaca, isi 'TIDAK TERBACA'"
    )

    tempat_lahir: Optional[str] = Field(
        default=None, description="Tempat lahir sesuai dokumen. Opsional."
    )

    jenis_kelamin: Optional[str] = Field(
        default=None, description="Jenis kelamin: 'LAKI-LAKI' atau 'PEREMPUAN'"
    )

    alamat: Optional[str] = Field(
        default=None, description="Alamat lengkap sesuai dokumen"
    )

    tanggal_kadaluarsa: str = Field(
        description="Tanggal kadaluarsa dokumen dalam format DD-MM-YYYY. Untuk KTP seumur hidup, isi 'SEUMUR HIDUP'"
    )

    jenis_dokumen: DocumentType = Field(
        description="Jenis dokumen: 'KTP', 'PASPOR', 'SIM', atau 'UNKNOWN'"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Tingkat keyakinan ekstraksi (0.0 - 1.0). 1.0 = sangat jelas, 0.5 = sebagian terbaca, 0.0 = tidak terbaca",
    )

    catatan: Optional[str] = Field(
        default=None,
        description="Catatan tambahan tentang kualitas gambar atau masalah ekstraksi",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "nama": "BUDI SANTOSO",
                "nik": "3201234567890001",
                "tanggal_lahir": "15-08-1990",
                "tempat_lahir": "JAKARTA",
                "jenis_kelamin": "LAKI-LAKI",
                "alamat": "JL. MERDEKA NO. 123",
                "tanggal_kadaluarsa": "SEUMUR HIDUP",
                "jenis_dokumen": "KTP",
                "confidence": 0.95,
                "catatan": None,
            }
        }
    }
