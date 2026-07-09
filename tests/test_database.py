from pathlib import Path

import pytest

from src.database import Database, Customer, AuditLogEntry, Base


@pytest.fixture
def db(temp_db_path: Path) -> Database:
    return Database(db_path=temp_db_path)


class TestDatabase:
    def test_save_and_get_customer(self, db: Database):
        result = db.save_customer(
            {"nama": "Test", "nik": "1234567890123456"},
            {"status": "APPROVED", "account_type": "Futures"},
            pii_fields_count=2,
        )
        assert result["customer_id"].startswith("CUST-")
        assert result["validation_status"] == "APPROVED"
        assert result["account_type"] == "Futures"
        assert result["pii_fields_count"] == 2
        assert result["pii_masked"] is True

    def test_save_without_pii_masking(self, db: Database):
        result = db.save_customer(
            {"nama": "Test Raw", "nik": "1234567890123456"},
            {"status": "APPROVED", "account_type": "Stocks"},
            pii_masked=False,
            pii_fields_count=0,
        )
        assert result["pii_masked"] is False
        assert result["pii_fields_count"] == 0

    def test_get_customers_empty(self, db: Database):
        customers = db.get_customers()
        assert customers == []

    def test_get_customers_multiple(self, db: Database):
        db.save_customer({"nama": "A"}, {"status": "APPROVED", "account_type": "Stocks"})
        db.save_customer({"nama": "B"}, {"status": "REJECTED", "account_type": "Crypto"})

        customers = db.get_customers()
        assert len(customers) == 2
        assert customers[0]["validation_status"] == "APPROVED"
        assert customers[1]["validation_status"] == "REJECTED"

    def test_audit_log_created(self, db: Database):
        result = db.save_customer(
            {"nama": "Test"}, {"status": "APPROVED", "account_type": "Stocks"}
        )
        logs = db.get_audit_logs()
        assert len(logs) == 1
        assert logs[0]["customer_id"] == result["customer_id"]
        assert logs[0]["action"] == "CUSTOMER_SAVED"

    def test_audit_log_multiple_entries(self, db: Database):
        db.save_customer({"nama": "A"}, {"status": "APPROVED", "account_type": "Stocks"})
        db.save_customer({"nama": "B"}, {"status": "REJECTED", "account_type": "Crypto"})

        logs = db.get_audit_logs()
        assert len(logs) == 2

    def test_document_data_persisted(self, db: Database):
        doc = {"nama": "BUDI SANTOSO", "nik": "3201234567890001", "alamat": "JL. MERDEKA"}
        db.save_customer(doc, {"status": "APPROVED", "account_type": "Futures"})

        customers = db.get_customers()
        assert customers[0]["document_data"]["nama"] == "BUDI SANTOSO"
        assert customers[0]["document_data"]["nik"] == "3201234567890001"

    def test_multiple_db_instances_same_file(self, temp_db_path: Path):
        db1 = Database(db_path=temp_db_path)
        db1.save_customer({"nama": "A"}, {"status": "APPROVED", "account_type": "Stocks"})

        db2 = Database(db_path=temp_db_path)
        customers = db2.get_customers()
        assert len(customers) == 1
        assert customers[0]["document_data"]["nama"] == "A"
