import json
from pathlib import Path

import pytest


def load_cases():
    cases_file = Path(__file__).parent / "test_cases.json"
    with open(cases_file, encoding="utf-8") as f:
        return json.load(f)


class TestTestCaseStructure:
    def test_cases_load_successfully(self):
        cases = load_cases()
        assert len(cases) >= 5

    def test_each_case_has_required_fields(self):
        cases = load_cases()
        for case in cases:
            assert "id" in case, f"Case missing 'id': {case}"
            assert "document_data" in case, f"{case['id']}: missing document_data"
            assert "expected" in case, f"{case['id']}: missing expected"
            assert "account_type" in case, f"{case['id']}: missing account_type"

    def test_each_doc_has_required_fields(self):
        required = {"nama", "nik", "tanggal_lahir", "tanggal_kadaluarsa", "jenis_dokumen", "confidence"}
        cases = load_cases()
        for case in cases:
            doc = case["document_data"]
            assert required.issubset(doc.keys()), f"{case['id']}: missing {required - doc.keys()}"

    def test_confidence_is_float(self):
        cases = load_cases()
        for case in cases:
            assert isinstance(case["document_data"]["confidence"], float), f"{case['id']}: confidence not float"

    def test_all_ids_unique(self):
        cases = load_cases()
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[id for id in ids if ids.count(id) > 1]}"
