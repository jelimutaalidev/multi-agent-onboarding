"""
PII Guardian - Security Agent untuk proteksi data sensitif.

Agent ini bertugas:
1. Mendeteksi dan masking data PII (Personally Identifiable Information)
2. Memastikan data aman sebelum di-log ke database simulasi
3. Mendukung data sensitif Indonesia (NIK, No HP, dll)
"""

import re
import hashlib
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from .database import Database


# ========== ENUMS ==========


class MaskingStrategy(str, Enum):
    """Strategi masking PII"""

    REDACT = "redact"  # Ganti dengan [REDACTED]
    MASK = "mask"  # Partial masking (123xxxx)
    HASH = "hash"  # Hash deterministik
    TOKENIZE = "tokenize"  # Ganti dengan token unik


class PIIType(str, Enum):
    """Jenis data PII yang dideteksi"""

    NIK = "nik"
    PHONE = "phone"
    EMAIL = "email"
    NAME = "name"
    ADDRESS = "address"
    BIRTH_DATE = "birth_date"
    CREDIT_CARD = "credit_card"


# ========== SCHEMAS ==========


class PIIDetection(BaseModel):
    """Hasil deteksi PII"""

    pii_type: PIIType
    original_value: str
    masked_value: str
    position: tuple[int, int]  # (start, end) position in text


class MaskedData(BaseModel):
    """Data yang sudah di-mask"""

    original_fields: Dict[str, Any] = Field(description="Field names yang di-mask")
    masked_data: Dict[str, Any] = Field(
        description="Data dengan nilai yang sudah di-mask"
    )
    pii_detections: List[PIIDetection] = Field(description="Detail PII yang terdeteksi")
    masking_timestamp: str = Field(description="Timestamp masking")


# ========== PII PATTERNS (Indonesia-specific) ==========

PII_PATTERNS = {
    PIIType.NIK: {
        "pattern": r"\b\d{16}\b",
        "description": "NIK (16 digit)",
        "mask_func": lambda x: x[:4] + "xxxx" + x[8:12] + "xxxx",  # 1234xxxx5678xxxx
    },
    PIIType.PHONE: {
        "pattern": r"\b(?:08|\+62|62)\d{8,12}\b",
        "description": "Nomor telepon Indonesia",
        "mask_func": lambda x: x[:4] + "xxxx" + x[-4:],  # 0812xxxxxxxx1234
    },
    PIIType.EMAIL: {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "description": "Alamat email",
        "mask_func": lambda x: x[0] + "***@" + x.split("@")[1]
        if "@" in x
        else "[REDACTED]",
    },
    PIIType.CREDIT_CARD: {
        "pattern": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "description": "Nomor kartu kredit",
        "mask_func": lambda x: "xxxx-xxxx-xxxx-" + re.sub(r"[-\s]", "", x)[-4:],
    },
    PIIType.BIRTH_DATE: {
        "pattern": r"\b\d{2}[-/]\d{2}[-/]\d{4}\b",
        "description": "Tanggal lahir (DD-MM-YYYY)",
        "mask_func": lambda x: "xx-xx-" + x[-4:],  # xx-xx-1990
    },
}


# ========== CORE FUNCTIONS ==========


def detect_pii(text: str) -> List[PIIDetection]:
    """
    Deteksi semua PII dalam teks.

    Args:
        text: Teks yang akan diperiksa

    Returns:
        List[PIIDetection]: Daftar PII yang terdeteksi
    """
    detections = []

    for pii_type, config in PII_PATTERNS.items():
        pattern = config["pattern"]
        mask_func = config["mask_func"]

        for match in re.finditer(pattern, text):
            original = match.group()
            masked = mask_func(original)

            detections.append(
                PIIDetection(
                    pii_type=pii_type,
                    original_value=original,
                    masked_value=masked,
                    position=(match.start(), match.end()),
                )
            )

    return detections


def mask_text(
    text: str, strategy: MaskingStrategy = MaskingStrategy.MASK
) -> tuple[str, List[PIIDetection]]:
    """
    Mask semua PII dalam teks.

    Args:
        text: Teks yang akan di-mask
        strategy: Strategi masking

    Returns:
        tuple: (teks yang sudah di-mask, list detections)
    """
    detections = detect_pii(text)
    masked_text = text

    # Sort by position descending agar replacement tidak menggeser posisi
    sorted_detections = sorted(detections, key=lambda x: x.position[0], reverse=True)

    for detection in sorted_detections:
        start, end = detection.position

        if strategy == MaskingStrategy.REDACT:
            replacement = f"[REDACTED_{detection.pii_type.value.upper()}]"
        elif strategy == MaskingStrategy.MASK:
            replacement = detection.masked_value
        elif strategy == MaskingStrategy.HASH:
            hash_val = hashlib.sha256(detection.original_value.encode()).hexdigest()[
                :12
            ]
            replacement = f"[HASH:{hash_val}]"
        else:  # TOKENIZE
            replacement = (
                f"[TOKEN:{detection.pii_type.value}_{id(detection) % 10000:04d}]"
            )

        masked_text = masked_text[:start] + replacement + masked_text[end:]
        detection.masked_value = replacement

    return masked_text, detections


def mask_dict(
    data: Dict[str, Any],
    sensitive_fields: Optional[List[str]] = None,
    strategy: MaskingStrategy = MaskingStrategy.MASK,
) -> MaskedData:
    """
    Mask PII dalam dictionary data.

    Args:
        data: Dictionary data yang akan di-mask
        sensitive_fields: List field yang dianggap sensitif (optional)
        strategy: Strategi masking

    Returns:
        MaskedData: Data yang sudah di-mask dengan metadata
    """
    # Default sensitive fields untuk dokumen Indonesia
    if sensitive_fields is None:
        sensitive_fields = ["nik", "nama", "alamat", "tanggal_lahir", "phone", "email"]

    masked_data = data.copy()
    all_detections = []
    masked_fields = {}

    for key, value in data.items():
        if value is None:
            continue

        if isinstance(value, str):
            # Selalu mask jika field ada di sensitive_fields
            if key.lower() in [f.lower() for f in sensitive_fields]:
                masked_value, detections = mask_text(value, strategy)

                # Jika tidak ada pattern match tapi field sensitif, tetap mask
                if not detections and key.lower() == "nik":
                    # NIK specific handling
                    if len(value) == 16 and value.isdigit():
                        masked_value = value[:4] + "xxxx" + value[8:12] + "xxxx"
                        detections = [
                            PIIDetection(
                                pii_type=PIIType.NIK,
                                original_value=value,
                                masked_value=masked_value,
                                position=(0, len(value)),
                            )
                        ]
                elif not detections and key.lower() == "nama":
                    # Name masking - keep first 3 chars
                    if len(value) > 3:
                        masked_value = value[:3] + "***"
                        detections = [
                            PIIDetection(
                                pii_type=PIIType.NAME,
                                original_value=value,
                                masked_value=masked_value,
                                position=(0, len(value)),
                            )
                        ]
                elif not detections and key.lower() == "alamat":
                    # Address masking - keep first word
                    words = value.split()
                    if len(words) > 1:
                        masked_value = words[0] + " [REDACTED]"
                        detections = [
                            PIIDetection(
                                pii_type=PIIType.ADDRESS,
                                original_value=value,
                                masked_value=masked_value,
                                position=(0, len(value)),
                            )
                        ]

                if detections:
                    masked_data[key] = masked_value
                    masked_fields[key] = value  # Store original
                    all_detections.extend(detections)
            else:
                # Check for PII patterns in non-sensitive fields too
                masked_value, detections = mask_text(value, strategy)
                if detections:
                    masked_data[key] = masked_value
                    masked_fields[key] = value
                    all_detections.extend(detections)

    return MaskedData(
        original_fields=masked_fields,
        masked_data=masked_data,
        pii_detections=all_detections,
        masking_timestamp=datetime.now().isoformat(),
    )


def mask_document_data(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask data hasil ekstraksi dokumen.

    Fungsi convenience untuk mask data dari Document Extractor.

    Args:
        document_data: Data dari extract_document_data()

    Returns:
        dict: Data yang sudah di-mask
    """
    result = mask_dict(document_data)
    return result.masked_data


def process_and_save_customer(
    document_data: Dict[str, Any], validation_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process dan simpan data customer dengan PII protection.

    Convenience function yang menggabungkan masking dan penyimpanan.

    Args:
        document_data: Data dari Document Extractor
        validation_result: Hasil dari Policy Validator

    Returns:
        dict: Record yang disimpan
    """
    masked_result = mask_dict(document_data)
    db = Database()
    return db.save_customer(
        masked_result.masked_data,
        validation_result,
        pii_masked=True,
        pii_fields_count=len(masked_result.pii_detections),
    )


def get_pii_report(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate laporan PII dari data dokumen.

    Args:
        document_data: Data dari Document Extractor

    Returns:
        dict: Laporan PII
    """
    result = mask_dict(document_data)

    return {
        "total_pii_found": len(result.pii_detections),
        "pii_types": list(set(d.pii_type.value for d in result.pii_detections)),
        "masked_fields": list(result.original_fields.keys()),
        "masked_data": result.masked_data,
        "timestamp": result.masking_timestamp,
    }
