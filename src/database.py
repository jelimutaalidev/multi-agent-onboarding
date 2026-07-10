"""Database module with SQLAlchemy + SQLite.

Replaces the JSON-based SimulatedDatabase with a concurrent-safe,
queryable SQLite backend.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, Session

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "onboarding.db"

Base = declarative_base()


class Customer(Base):
    """Customer record with masked document data and validation status."""

    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    document_data = Column(JSON, comment="Document data after PII masking")
    validation_status = Column(String, comment="APPROVED / REJECTED / PENDING_REVIEW")
    account_type = Column(String, comment="Jenis akun trading")
    pii_masked = Column(Integer, default=1, comment="1 jika PII sudah di-mask")
    pii_fields_count = Column(
        Integer, default=0, comment="Jumlah field PII yang di-mask"
    )
    created_at = Column(
        DateTime, default=datetime.utcnow, comment="Waktu pembuatan record"
    )


class AuditLogEntry(Base):
    """Audit trail untuk setiap operasi penyimpanan customer."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, nullable=True, comment="Referensi ke Customer.id")
    action = Column(String, comment="Nama operasi (CUSTOMER_SAVED, dll)")
    timestamp = Column(DateTime, default=datetime.utcnow, comment="Waktu operasi")
    detail = Column(Text, nullable=True, comment="Detail tambahan operasi")


class Database:
    """SQLite database wrapper for customer and audit log storage."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path ke file SQLite. Default: data/db/onboarding.db
        """
        if db_path is None:
            db_path = DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)

    def save_customer(
        self,
        document_data: dict,
        validation_result: dict,
        pii_fields_count: int = 0,
        pii_masked: bool = True,
    ) -> dict:
        """
        Simpan data customer dan audit log ke database.

        Args:
            document_data: Data dokumen (sudah di-mask jika perlu)
            validation_result: Hasil validasi dengan keys status, account_type
            pii_fields_count: Jumlah field PII yang di-mask
            pii_masked: Apakah data sudah di-mask

        Returns:
            dict: Record yang tersimpan dengan customer_id dan metadata
        """
        customer_id = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        with Session(self.engine) as session:
            customer = Customer(
                id=customer_id,
                document_data=document_data,
                validation_status=validation_result.get("status"),
                account_type=validation_result.get("account_type"),
                pii_masked=1 if pii_masked else 0,
                pii_fields_count=pii_fields_count,
            )
            session.add(customer)

            audit = AuditLogEntry(
                customer_id=customer_id,
                action="CUSTOMER_SAVED",
                detail=f"masked={pii_masked}, fields={pii_fields_count}",
            )
            session.add(audit)
            session.commit()

        return {
            "customer_id": customer_id,
            "document_data": document_data,
            "validation_status": validation_result.get("status"),
            "account_type": validation_result.get("account_type"),
            "created_at": datetime.now().isoformat(),
            "pii_masked": pii_masked,
            "pii_fields_count": pii_fields_count,
        }

    def get_customers(self) -> list[dict]:
        """
        Ambil semua data customer.

        Returns:
            list[dict]: Daftar customer yang tersimpan
        """
        with Session(self.engine) as session:
            rows = session.query(Customer).all()
            return [
                {
                    "customer_id": r.id,
                    "document_data": r.document_data,
                    "validation_status": r.validation_status,
                    "account_type": r.account_type,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "pii_masked": bool(r.pii_masked),
                    "pii_fields_count": r.pii_fields_count,
                }
                for r in rows
            ]

    def get_audit_logs(self) -> list[dict]:
        """
        Ambil semua audit log entries.

        Returns:
            list[dict]: Daftar audit log
        """
        with Session(self.engine) as session:
            rows = session.query(AuditLogEntry).all()
            return [
                {
                    "id": r.id,
                    "customer_id": r.customer_id,
                    "action": r.action,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "detail": r.detail,
                }
                for r in rows
            ]
