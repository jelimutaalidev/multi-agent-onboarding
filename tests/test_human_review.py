from src.schemas import ReviewRequest


class TestReviewRequest:
    def test_has_required_fields(self):
        review = ReviewRequest(
            customer_name="BUDI SANTOSO",
            confidence=0.55,
            reason="Kualitas dokumen kurang jelas",
            document_data={"nik": "3201xxxxxxx001"},
        )
        assert review.review_id.startswith("REVIEW-")
        assert review.status == "PENDING_REVIEW"

    def test_default_status(self):
        review = ReviewRequest(
            customer_name="Test", confidence=0.5, reason="test", document_data={}
        )
        assert review.status == "PENDING_REVIEW"

    def test_unique_ids(self):
        r1 = ReviewRequest(
            customer_name="A", confidence=0.5, reason="test", document_data={}
        )
        r2 = ReviewRequest(
            customer_name="A", confidence=0.5, reason="test", document_data={}
        )
        assert r1.review_id != r2.review_id

    def test_created_at_set(self):
        review = ReviewRequest(
            customer_name="Test", confidence=0.5, reason="test", document_data={}
        )
        assert review.created_at is not None
        assert "T" in review.created_at  # ISO format has T separator

    def test_model_dump(self):
        review = ReviewRequest(
            customer_name="BUDI SANTOSO",
            confidence=0.55,
            reason="Kualitas dokumen kurang jelas",
            document_data={"nik": "3201xxxxxxx001"},
        )
        d = review.model_dump()
        assert d["customer_name"] == "BUDI SANTOSO"
        assert d["status"] == "PENDING_REVIEW"
        assert d["confidence"] == 0.55
