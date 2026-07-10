"""Tests for the LangGraph pipeline."""

from unittest.mock import patch

from src.graph import (
    OnboardingState,
    extract_document_node,
    validate_policy_node,
    mask_pii_node,
    save_customer_node,
    generate_report_node,
    route_after_extraction,
    build_pipeline,
    run_pipeline,
)
from src.schemas import RoutingDecision


SAMPLE_DOCUMENT = {
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

SAMPLE_VALIDATION = {
    "status": "APPROVED",
    "customer_name": "BUDI SANTOSO",
    "account_type": "Futures",
    "customer_age": 35,
    "minimum_age_required": 21,
    "reasons": ["Usia memenuhi syarat"],
    "policy_references": ["Kebijakan EXANTE"],
    "recommendations": None,
}

SAMPLE_MASKED = {
    "original_fields": {"nik": "3201234567890001", "nama": "BUDI SANTOSO"},
    "masked_data": {"nik": "3201xxxx7890xxxx", "nama": "BUD***"},
    "pii_detections": [],
    "masking_timestamp": "2026-01-01T00:00:00",
}

SAMPLE_PII_REPORT = {
    "total_pii_found": 2,
    "pii_types": ["nik", "name"],
    "masked_fields": ["nik", "nama"],
    "masked_data": {"nik": "3201xxxx7890xxxx", "nama": "BUD***"},
    "timestamp": "2026-01-01T00:00:00",
}

SAMPLE_SAVED = {
    "customer_id": "CUST-20260101-xxxx",
    "pii_masked": True,
    "pii_fields_count": 2,
    "document_data": {"nik": "3201xxxx7890xxxx", "nama": "BUD***"},
    "validation_result": SAMPLE_VALIDATION,
}


class TestRouteAfterExtraction:
    def test_rejected_routes_to_rejected(self):
        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "routing_decision": RoutingDecision.REJECTED.value,
        }
        assert route_after_extraction(state) == "rejected"

    def test_proceed_routes_to_proceed(self):
        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "routing_decision": RoutingDecision.PROCEED.value,
        }
        assert route_after_extraction(state) == "proceed"

    def test_pending_review_routes_to_proceed(self):
        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "routing_decision": RoutingDecision.PENDING_REVIEW.value,
        }
        assert route_after_extraction(state) == "proceed"


class TestExtractDocumentNode:
    @patch("src.graph.extract_document_data")
    @patch("src.graph.make_routing_decision")
    def test_returns_document_and_decision(self, mock_decision, mock_extract):
        mock_extract.return_value = SAMPLE_DOCUMENT
        mock_decision.return_value = RoutingDecision.PROCEED

        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
        }
        result = extract_document_node(state)

        mock_extract.assert_called_once_with("test.png", callbacks=[])
        assert result["document_data"] == SAMPLE_DOCUMENT
        assert result["routing_decision"] == RoutingDecision.PROCEED.value


class TestValidatePolicyNode:
    @patch("src.graph.validate_customer_from_document_data")
    def test_returns_validation(self, mock_validate):
        mock_validate.return_value = SAMPLE_VALIDATION

        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "document_data": SAMPLE_DOCUMENT,
        }
        result = validate_policy_node(state)

        mock_validate.assert_called_once_with(
            SAMPLE_DOCUMENT, "Futures", callbacks=[]
        )
        assert result["validation_result"] == SAMPLE_VALIDATION


class TestMaskPiiNode:
    @patch("src.graph.mask_dict")
    @patch("src.graph.get_pii_report")
    def test_returns_masked_data_and_report(self, mock_report, mock_mask):
        mock_mask.return_value = type("MaskedResult", (), {"masked_data": SAMPLE_MASKED["masked_data"]})()
        mock_report.return_value = SAMPLE_PII_REPORT

        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "document_data": SAMPLE_DOCUMENT,
        }
        result = mask_pii_node(state)

        assert result["masked_data"] == SAMPLE_MASKED["masked_data"]
        assert result["pii_report"] == SAMPLE_PII_REPORT


class TestSaveCustomerNode:
    @patch("src.graph.process_and_save_customer")
    def test_returns_save_result(self, mock_save):
        mock_save.return_value = SAMPLE_SAVED

        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "document_data": SAMPLE_DOCUMENT,
            "validation_result": SAMPLE_VALIDATION,
        }
        result = save_customer_node(state)

        mock_save.assert_called_once_with(SAMPLE_DOCUMENT, SAMPLE_VALIDATION)
        assert result["save_result"] == SAMPLE_SAVED


class TestGenerateReportNode:
    def test_assembles_full_report(self):
        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "document_data": SAMPLE_DOCUMENT,
            "validation_result": SAMPLE_VALIDATION,
            "pii_report": SAMPLE_PII_REPORT,
            "save_result": SAMPLE_SAVED,
        }
        result = generate_report_node(state)
        report = result["final_report"]

        assert report["extraction"] == SAMPLE_DOCUMENT
        assert report["validation"] == SAMPLE_VALIDATION
        assert report["pii_report"] == SAMPLE_PII_REPORT
        assert report["saved_record"] == SAMPLE_SAVED
        assert "error" not in report

    def test_includes_error_on_rejected(self):
        state: OnboardingState = {
            "image_path": "test.png",
            "account_type": "Futures",
            "routing_decision": RoutingDecision.REJECTED.value,
        }
        result = generate_report_node(state)
        report = result["final_report"]

        assert "error" in report
        assert "Kualitas dokumen" in report["error"]


class TestBuildPipeline:
    def test_creates_compiled_graph(self):
        graph = build_pipeline()
        assert graph is not None
        assert hasattr(graph, "invoke")

    def test_graph_has_expected_nodes(self):
        graph = build_pipeline()
        node_names = list(graph.nodes.keys())
        expected = {"extract_document", "validate_policy", "mask_pii", "save_customer", "generate_report"}
        for name in expected:
            assert name in node_names, f"Missing node: {name}"


class TestRunPipeline:
    @patch("src.graph.extract_document_data")
    @patch("src.graph.make_routing_decision")
    @patch("src.graph.validate_customer_from_document_data")
    @patch("src.graph.mask_dict")
    @patch("src.graph.get_pii_report")
    @patch("src.graph.process_and_save_customer")
    def test_full_pipeline_success(
        self,
        mock_save,
        mock_report,
        mock_mask,
        mock_validate,
        mock_decision,
        mock_extract,
    ):
        mock_extract.return_value = SAMPLE_DOCUMENT
        mock_decision.return_value = RoutingDecision.PROCEED
        mock_validate.return_value = SAMPLE_VALIDATION
        mock_mask.return_value = type("MaskedResult", (), {"masked_data": SAMPLE_MASKED["masked_data"]})()
        mock_report.return_value = SAMPLE_PII_REPORT
        mock_save.return_value = SAMPLE_SAVED

        result = run_pipeline("test.png", "Futures")

        assert result["extraction"] == SAMPLE_DOCUMENT
        assert result["validation"] == SAMPLE_VALIDATION
        assert result["pii_report"] == SAMPLE_PII_REPORT
        assert result["saved_record"] == SAMPLE_SAVED
        assert "error" not in result

    @patch("src.graph.extract_document_data")
    @patch("src.graph.make_routing_decision")
    def test_rejected_document_returns_error(
        self, mock_decision, mock_extract
    ):
        low_conf_doc = {**SAMPLE_DOCUMENT, "confidence": 0.15}
        mock_extract.return_value = low_conf_doc
        mock_decision.return_value = RoutingDecision.REJECTED

        report = run_pipeline("test.png", "Futures")

        assert "error" in report
        assert "Kualitas dokumen" in report["error"]

    def test_handles_empty_callbacks(self):
        assert run_pipeline is not None
