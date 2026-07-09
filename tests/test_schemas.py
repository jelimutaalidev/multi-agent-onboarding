import pytest

from src.schemas import DocumentData, DocumentType


class TestDocumentData:
    def test_valid_document(self):
        doc = DocumentData(
            nama="BUDI SANTOSO",
            nik="3201234567890001",
            tanggal_lahir="15-08-1990",
            tanggal_kadaluarsa="SEUMUR HIDUP",
            jenis_dokumen=DocumentType.KTP,
            confidence=0.95,
        )
        assert doc.nama == "BUDI SANTOSO"
        assert doc.nik == "3201234567890001"
        assert doc.jenis_dokumen == DocumentType.KTP
        assert doc.confidence == 0.95
        assert doc.catatan is None

    def test_invalid_confidence_low(self):
        with pytest.raises(Exception):
            DocumentData(
                nama="TEST",
                nik="1234567890123456",
                tanggal_lahir="01-01-2000",
                tanggal_kadaluarsa="SEUMUR HIDUP",
                jenis_dokumen=DocumentType.KTP,
                confidence=-0.1,
            )

    def test_invalid_confidence_high(self):
        with pytest.raises(Exception):
            DocumentData(
                nama="TEST",
                nik="1234567890123456",
                tanggal_lahir="01-01-2000",
                tanggal_kadaluarsa="SEUMUR HIDUP",
                jenis_dokumen=DocumentType.KTP,
                confidence=1.5,
            )

    def test_default_optional_fields(self):
        doc = DocumentData(
            nama="TEST",
            nik="1234567890123456",
            tanggal_lahir="01-01-2000",
            tanggal_kadaluarsa="SEUMUR HIDUP",
            jenis_dokumen=DocumentType.KTP,
            confidence=0.5,
        )
        assert doc.tempat_lahir is None
        assert doc.jenis_kelamin is None
        assert doc.alamat is None
        assert doc.catatan is None

    def test_model_dump(self):
        doc = DocumentData(
            nama="BUDI SANTOSO",
            nik="3201234567890001",
            tanggal_lahir="15-08-1990",
            tanggal_kadaluarsa="SEUMUR HIDUP",
            jenis_dokumen=DocumentType.KTP,
            confidence=0.95,
        )
        d = doc.model_dump()
        assert d["nama"] == "BUDI SANTOSO"
        assert d["jenis_dokumen"] == "KTP"

    def test_unknown_document_type(self):
        doc = DocumentData(
            nama="TIDAK TERBACA",
            nik="TIDAK TERBACA",
            tanggal_lahir="TIDAK TERBACA",
            tanggal_kadaluarsa="TIDAK TERBACA",
            jenis_dokumen=DocumentType.UNKNOWN,
            confidence=0.0,
        )
        assert doc.jenis_dokumen == DocumentType.UNKNOWN
        assert doc.confidence == 0.0
