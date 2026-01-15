"""
PII Guardian - Security Agent untuk proteksi data sensitif.

Agent ini bertugas:
1. Mendeteksi dan masking data PII (Personally Identifiable Information)
2. Memastikan data aman sebelum di-log ke database simulasi
3. Mendukung data sensitif Indonesia (NIK, No HP, dll)
"""

import re
import json
import hashlib
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path

from pydantic import BaseModel, Field


# ========== ENUMS ==========

class MaskingStrategy(str, Enum):
    """Strategi masking PII"""
    REDACT = "redact"      # Ganti dengan [REDACTED]
    MASK = "mask"          # Partial masking (123xxxx)
    HASH = "hash"          # Hash deterministik
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
    masked_data: Dict[str, Any] = Field(description="Data dengan nilai yang sudah di-mask")
    pii_detections: List[PIIDetection] = Field(description="Detail PII yang terdeteksi")
    masking_timestamp: str = Field(description="Timestamp masking")


# ========== PII PATTERNS (Indonesia-specific) ==========

PII_PATTERNS = {
    PIIType.NIK: {
        "pattern": r"\b\d{16}\b",
        "description": "NIK (16 digit)",
        "mask_func": lambda x: x[:4] + "xxxx" + x[8:12] + "xxxx"  # 1234xxxx5678xxxx
    },
    PIIType.PHONE: {
        "pattern": r"\b(?:08|\+62|62)\d{8,12}\b",
        "description": "Nomor telepon Indonesia",
        "mask_func": lambda x: x[:4] + "xxxx" + x[-4:]  # 0812xxxxxxxx1234
    },
    PIIType.EMAIL: {
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "description": "Alamat email",
        "mask_func": lambda x: x[0] + "***@" + x.split("@")[1] if "@" in x else "[REDACTED]"
    },
    PIIType.CREDIT_CARD: {
        "pattern": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "description": "Nomor kartu kredit",
        "mask_func": lambda x: "xxxx-xxxx-xxxx-" + re.sub(r"[-\s]", "", x)[-4:]
    },
    PIIType.BIRTH_DATE: {
        "pattern": r"\b\d{2}[-/]\d{2}[-/]\d{4}\b",
        "description": "Tanggal lahir (DD-MM-YYYY)",
        "mask_func": lambda x: "xx-xx-" + x[-4:]  # xx-xx-1990
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
            
            detections.append(PIIDetection(
                pii_type=pii_type,
                original_value=original,
                masked_value=masked,
                position=(match.start(), match.end())
            ))
    
    return detections


def mask_text(text: str, strategy: MaskingStrategy = MaskingStrategy.MASK) -> tuple[str, List[PIIDetection]]:
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
            hash_val = hashlib.sha256(detection.original_value.encode()).hexdigest()[:12]
            replacement = f"[HASH:{hash_val}]"
        else:  # TOKENIZE
            replacement = f"[TOKEN:{detection.pii_type.value}_{id(detection) % 10000:04d}]"
        
        masked_text = masked_text[:start] + replacement + masked_text[end:]
        detection.masked_value = replacement
    
    return masked_text, detections


def mask_dict(
    data: Dict[str, Any],
    sensitive_fields: Optional[List[str]] = None,
    strategy: MaskingStrategy = MaskingStrategy.MASK
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
                        detections = [PIIDetection(
                            pii_type=PIIType.NIK,
                            original_value=value,
                            masked_value=masked_value,
                            position=(0, len(value))
                        )]
                elif not detections and key.lower() == "nama":
                    # Name masking - keep first 3 chars
                    if len(value) > 3:
                        masked_value = value[:3] + "***"
                        detections = [PIIDetection(
                            pii_type=PIIType.NAME,
                            original_value=value,
                            masked_value=masked_value,
                            position=(0, len(value))
                        )]
                elif not detections and key.lower() == "alamat":
                    # Address masking - keep first word
                    words = value.split()
                    if len(words) > 1:
                        masked_value = words[0] + " [REDACTED]"
                        detections = [PIIDetection(
                            pii_type=PIIType.ADDRESS,
                            original_value=value,
                            masked_value=masked_value,
                            position=(0, len(value))
                        )]
                
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
        masking_timestamp=datetime.now().isoformat()
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


# ========== DATABASE SIMULATION ==========

class SimulatedDatabase:
    """
    Database simulasi untuk menyimpan data nasabah.
    
    Semua data yang masuk akan di-mask sebelum disimpan.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database simulasi."""
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "db"
        
        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.customers_file = self.db_path / "customers.json"
        self.audit_log_file = self.db_path / "audit_log.json"
        
        # Initialize files if not exist
        if not self.customers_file.exists():
            self._write_json(self.customers_file, {"customers": []})
        if not self.audit_log_file.exists():
            self._write_json(self.audit_log_file, {"logs": []})
    
    def _read_json(self, path: Path) -> dict:
        """Read JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _write_json(self, path: Path, data: dict):
        """Write JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_customer(
        self,
        document_data: Dict[str, Any],
        validation_result: Dict[str, Any],
        mask_pii: bool = True
    ) -> Dict[str, Any]:
        """
        Simpan data nasabah ke database.
        
        Data akan otomatis di-mask jika mask_pii=True.
        
        Args:
            document_data: Data dari Document Extractor
            validation_result: Hasil dari Policy Validator
            mask_pii: Apakah data PII harus di-mask
            
        Returns:
            dict: Record yang disimpan (sudah di-mask)
        """
        # Mask data jika diperlukan
        if mask_pii:
            masked_result = mask_dict(document_data)
            safe_document_data = masked_result.masked_data
            pii_detections = [d.model_dump() for d in masked_result.pii_detections]
        else:
            safe_document_data = document_data
            pii_detections = []
        
        # Create customer record
        customer_id = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        record = {
            "customer_id": customer_id,
            "document_data": safe_document_data,
            "validation_status": validation_result.get("status"),
            "account_type": validation_result.get("account_type"),
            "created_at": datetime.now().isoformat(),
            "pii_masked": mask_pii,
            "pii_fields_count": len(pii_detections)
        }
        
        # Save to customers file
        db = self._read_json(self.customers_file)
        db["customers"].append(record)
        self._write_json(self.customers_file, db)
        
        # Log audit
        self._log_audit(
            action="CUSTOMER_SAVED",
            customer_id=customer_id,
            pii_masked=mask_pii,
            pii_detections_count=len(pii_detections)
        )
        
        return record
    
    def _log_audit(self, action: str, **kwargs):
        """Log aksi ke audit log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            **kwargs
        }
        
        audit = self._read_json(self.audit_log_file)
        audit["logs"].append(log_entry)
        self._write_json(self.audit_log_file, audit)
    
    def get_customers(self) -> List[Dict]:
        """Get semua customer records."""
        db = self._read_json(self.customers_file)
        return db["customers"]
    
    def get_audit_logs(self) -> List[Dict]:
        """Get semua audit logs."""
        audit = self._read_json(self.audit_log_file)
        return audit["logs"]


# ========== PII GUARDIAN AGENT ==========

def create_pii_guardian():
    """
    Create PII Guardian yang terintegrasi dengan LangChain middleware.
    
    Menggunakan PIIMiddleware bawaan LangChain untuk proteksi tambahan.
    """
    from langchain.agents import create_agent
    from langchain.agents.middleware import PIIMiddleware
    from langchain.tools import tool
    
    @tool
    def mask_sensitive_data(data_json: str) -> str:
        """
        Mask data sensitif dalam JSON string.
        
        Args:
            data_json: JSON string berisi data yang akan di-mask
            
        Returns:
            str: JSON string dengan data yang sudah di-mask
        """
        try:
            data = json.loads(data_json)
            result = mask_dict(data)
            return json.dumps(result.masked_data, ensure_ascii=False)
        except json.JSONDecodeError:
            return mask_text(data_json)[0]
    
    @tool
    def detect_pii_in_text(text: str) -> str:
        """
        Deteksi PII dalam teks dan return laporan.
        
        Args:
            text: Teks yang akan diperiksa
            
        Returns:
            str: Laporan PII yang ditemukan
        """
        detections = detect_pii(text)
        
        if not detections:
            return "Tidak ada PII yang terdeteksi."
        
        report = f"Ditemukan {len(detections)} PII:\n"
        for d in detections:
            report += f"- {d.pii_type.value}: {d.masked_value}\n"
        
        return report
    
    @tool
    def save_to_secure_database(
        document_data_json: str,
        validation_result_json: str
    ) -> str:
        """
        Simpan data ke database dengan masking otomatis.
        
        Args:
            document_data_json: JSON string data dokumen
            validation_result_json: JSON string hasil validasi
            
        Returns:
            str: Konfirmasi penyimpanan
        """
        try:
            doc_data = json.loads(document_data_json)
            val_result = json.loads(validation_result_json)
            
            db = SimulatedDatabase()
            record = db.save_customer(doc_data, val_result, mask_pii=True)
            
            return f"Data berhasil disimpan dengan ID: {record['customer_id']}. PII telah di-mask."
        except Exception as e:
            return f"Gagal menyimpan: {str(e)}"
    
    # Create agent with PII middleware
    agent = create_agent(
        model="google_genai:gemini-2.5-flash",
        tools=[mask_sensitive_data, detect_pii_in_text, save_to_secure_database],
        system_prompt="""Kamu adalah PII Guardian, security agent yang bertugas melindungi data sensitif.

TUGAS:
1. Mendeteksi PII (Personally Identifiable Information) dalam data
2. Melakukan masking pada data sensitif sebelum disimpan
3. Memastikan tidak ada data sensitif yang ter-log tanpa proteksi

DATA SENSITIF INDONESIA:
- NIK (16 digit): Mask menjadi 1234xxxx5678xxxx
- Nama: Mask menjadi 3 huruf pertama + ***
- Alamat: Mask menjadi kata pertama + [REDACTED]
- Tanggal Lahir: Mask menjadi xx-xx-YYYY
- No HP: Mask menjadi 0812xxxxxx1234
- Email: Mask menjadi a***@domain.com

Selalu gunakan tools yang tersedia untuk memproses data.""",
        middleware=[
            # Built-in LangChain PII protection
            PIIMiddleware(
                "email",
                strategy="mask",
                apply_to_input=True,
                apply_to_output=True
            ),
            PIIMiddleware(
                "credit_card",
                strategy="redact",
                apply_to_input=True,
                apply_to_output=True
            ),
            # Custom detector for NIK (16 digits)
            PIIMiddleware(
                "nik",
                detector=r"\b\d{16}\b",
                strategy="mask",
                apply_to_input=True,
                apply_to_output=True
            ),
        ]
    )
    
    return agent


# ========== CONVENIENCE FUNCTIONS ==========

def process_and_save_customer(
    document_data: Dict[str, Any],
    validation_result: Dict[str, Any]
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
    db = SimulatedDatabase()
    return db.save_customer(document_data, validation_result, mask_pii=True)


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
        "timestamp": result.masking_timestamp
    }
