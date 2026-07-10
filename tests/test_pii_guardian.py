
from src.pii_guardian import (
    detect_pii,
    mask_text,
    mask_dict,
    mask_document_data,
    get_pii_report,
    PIIType,
    MaskingStrategy,
)
from src.database import Database


class TestDetectPII:
    def test_detect_nik(self):
        detections = detect_pii("NIK saya adalah 3201234567890001")
        assert len(detections) >= 1
        nik_detections = [d for d in detections if d.pii_type == PIIType.NIK]
        assert len(nik_detections) == 1
        assert nik_detections[0].original_value == "3201234567890001"

    def test_detect_phone(self):
        detections = detect_pii("HP: 081234567890")
        phone_detections = [d for d in detections if d.pii_type == PIIType.PHONE]
        assert len(phone_detections) >= 1

    def test_detect_email(self):
        detections = detect_pii("Email: user@example.com")
        email_detections = [d for d in detections if d.pii_type == PIIType.EMAIL]
        assert len(email_detections) >= 1

    def test_detect_birth_date(self):
        detections = detect_pii("Lahir 15-08-1990")
        bd_detections = [d for d in detections if d.pii_type == PIIType.BIRTH_DATE]
        assert len(bd_detections) >= 1

    def test_no_pii_in_clean_text(self):
        detections = detect_pii("Halo, apa kabar?")
        assert len(detections) == 0

    def test_detect_credit_card(self):
        detections = detect_pii("Kartu: 1234-5678-9012-3456")
        cc_detections = [d for d in detections if d.pii_type == PIIType.CREDIT_CARD]
        assert len(cc_detections) >= 1


class TestMaskText:
    def test_mask_default_strategy(self):
        masked, detections = mask_text("NIK 3201234567890001")
        assert len(detections) >= 1
        nik_detections = [d for d in detections if d.pii_type == PIIType.NIK]
        assert len(nik_detections) >= 1
        assert "3201xxxx7890xxxx" in masked or "xxxx-xxxx-xxxx-0001" in masked

    def test_mask_redact_strategy(self):
        masked, detections = mask_text(
            "Email user@test.com", strategy=MaskingStrategy.REDACT
        )
        assert "[REDACTED_EMAIL]" in masked

    def test_mask_hash_strategy(self):
        masked, detections = mask_text(
            "3201234567890001", strategy=MaskingStrategy.HASH
        )
        assert "[HASH:" in masked

    def test_mask_multiple_pii(self):
        masked, detections = mask_text("NIK: 3201234567890001, Email: test@mail.com")
        assert len(detections) >= 2


class TestMaskDict:
    def test_mask_nik_field(self):
        data = {"nik": "3201234567890001", "nama": "BUDI SANTOSO"}
        result = mask_dict(data)
        assert "xxxx" in result.masked_data["nik"]
        assert "BUD" in result.masked_data["nama"]

    def test_mask_alamat_field(self):
        data = {"alamat": "JL. MERDEKA NO. 123, RT 001/RW 002"}
        result = mask_dict(data)
        assert "[REDACTED]" in result.masked_data["alamat"]

    def test_non_sensitive_field_unchanged(self):
        data = {
            "nama": "BUDI SANTOSO",
            "jenis_kelamin": "LAKI-LAKI",
            "confidence": 0.95,
        }
        result = mask_dict(data)
        assert result.masked_data["jenis_kelamin"] == "LAKI-LAKI"
        assert result.masked_data["confidence"] == 0.95

    def test_original_fields_tracked(self):
        data = {"nik": "3201234567890001", "nama": "BUDI SANTOSO"}
        result = mask_dict(data)
        assert "nik" in result.original_fields
        assert "nama" in result.original_fields
        assert result.original_fields["nik"] == "3201234567890001"

    def test_empty_dict(self):
        result = mask_dict({})
        assert result.masked_data == {}
        assert result.pii_detections == []
        assert result.original_fields == {}

    def test_none_values_skipped(self):
        data = {"nik": None, "nama": "Test"}
        result = mask_dict(data)
        assert result.masked_data["nik"] is None

    def test_pii_detections_metadata(self):
        data = {"nik": "3201234567890001", "alamat": "JL. MERDEKA NO. 123"}
        result = mask_dict(data)
        assert len(result.pii_detections) >= 2
        assert result.masking_timestamp is not None

    def test_custom_sensitive_fields(self):
        data = {"nik": "3201234567890001", "custom_phone": "081234567890"}
        result = mask_dict(data, sensitive_fields=["custom_phone"])
        assert result.masked_data["custom_phone"] != "081234567890"

    def test_mask_document_data_convenience(self):
        data = {"nik": "3201234567890001", "nama": "BUDI SANTOSO"}
        masked = mask_document_data(data)
        assert isinstance(masked, dict)
        assert "xxxx" in masked["nik"]


class TestGetPIIReport:
    def test_report_structure(self):
        data = {
            "nik": "3201234567890001",
            "nama": "BUDI SANTOSO",
            "alamat": "JL. MERDEKA",
        }
        report = get_pii_report(data)
        assert report["total_pii_found"] >= 3
        assert "nik" in report["pii_types"]
        assert "name" in report["pii_types"]
        assert "address" in report["pii_types"]
        assert len(report["masked_fields"]) >= 3
        assert report["timestamp"] is not None


class TestProcessAndSaveCustomer:
    def test_saves_with_masking(self, temp_db_path):
        from src.pii_guardian import process_and_save_customer

        db = Database(db_path=temp_db_path)
        import src.pii_guardian as pg

        original = pg.Database
        pg.Database = lambda db_path=None: db
        try:
            doc = {"nama": "BUDI SANTOSO", "nik": "3201234567890001"}
            val = {"status": "APPROVED", "account_type": "Futures"}
            record = process_and_save_customer(doc, val)
            assert record["customer_id"].startswith("CUST-")
            assert record["pii_fields_count"] >= 2
            assert record["pii_masked"] is True
            assert record["document_data"]["nik"] != doc["nik"]
        finally:
            pg.Database = original
