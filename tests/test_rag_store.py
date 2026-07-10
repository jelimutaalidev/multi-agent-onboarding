import pytest

from src.rag_store import (
    load_policy_documents,
    split_documents,
    get_embeddings,
    search_policies,
)
from langchain_core.documents import Document


class TestLoadPolicyDocuments:
    def test_load_policies(self):
        docs = load_policy_documents()
        assert len(docs) > 0
        assert all(hasattr(d, "page_content") for d in docs)

    def test_policy_content(self):
        docs = load_policy_documents()
        content = " ".join(d.page_content for d in docs).lower()
        assert "exante" in content

    def test_invalid_directory_raises(self, monkeypatch):
        from pathlib import Path

        monkeypatch.setattr("src.rag_store.POLICIES_DIR", Path("/nonexistent/path"))
        with pytest.raises(FileNotFoundError):
            load_policy_documents()


class TestSplitDocuments:
    def test_split_single_document(self):
        docs = [Document(page_content="A" * 1000)]
        splits = split_documents(docs)
        assert len(splits) >= 2
        for s in splits:
            assert len(s.page_content) <= 500

    def test_split_multiple_documents(self):
        docs = [Document(page_content="A" * 600), Document(page_content="B" * 600)]
        splits = split_documents(docs)
        assert len(splits) >= 4

    def test_empty_documents(self):
        splits = split_documents([])
        assert splits == []


class TestGetEmbeddings:
    def test_returns_singleton(self):
        e1 = get_embeddings()
        e2 = get_embeddings()
        assert e1 is e2


class TestSearchPolicies:
    @pytest.mark.integration
    def test_search_returns_results(self):
        results = search_policies("Futures trading age requirement", k=2)
        assert len(results) >= 1
        assert any("Futures" in r.page_content for r in results)

    @pytest.mark.integration
    def test_search_with_different_k(self):
        r1 = search_policies("trading", k=1)
        r2 = search_policies("trading", k=3)
        assert len(r2) >= len(r1)

    @pytest.mark.integration
    def test_search_empty_query(self):
        results = search_policies("xyznonexistent12345", k=2)
        assert len(results) >= 0
