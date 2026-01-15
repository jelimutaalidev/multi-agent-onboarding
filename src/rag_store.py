"""
RAG Store - Vector Store dan Retriever untuk Policy Documents.

Module ini mengelola indexing dan retrieval dokumen kebijakan
untuk Policy Validator Agent.
"""

import os
from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document


# Path ke folder policies
POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"

# Global vector store instance (singleton pattern)
_vector_store: Optional[InMemoryVectorStore] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Get or create HuggingFace embeddings model.
    
    Uses sentence-transformers/all-MiniLM-L6-v2 for efficient embeddings.
    """
    global _embeddings
    
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
    
    return _embeddings


def load_policy_documents() -> List[Document]:
    """
    Load semua dokumen kebijakan dari folder data/policies.
    
    Returns:
        List[Document]: List of Document objects
    """
    documents = []
    
    if not POLICIES_DIR.exists():
        raise FileNotFoundError(f"Folder policies tidak ditemukan: {POLICIES_DIR}")
    
    # Load semua file .txt dan .pdf
    for file_path in POLICIES_DIR.glob("*.txt"):
        loader = TextLoader(str(file_path), encoding="utf-8")
        docs = loader.load()
        documents.extend(docs)
    
    if not documents:
        raise ValueError("Tidak ada dokumen kebijakan yang ditemukan")
    
    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split documents menjadi chunks yang lebih kecil untuk indexing.
    
    Args:
        documents: List of Document objects
        
    Returns:
        List[Document]: List of chunked documents
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    splits = text_splitter.split_documents(documents)
    return splits


def initialize_vector_store(force_reload: bool = False) -> InMemoryVectorStore:
    """
    Initialize vector store dengan dokumen kebijakan.
    
    Args:
        force_reload: Jika True, reload dokumen meskipun sudah ada
        
    Returns:
        InMemoryVectorStore: Initialized vector store
    """
    global _vector_store
    
    if _vector_store is not None and not force_reload:
        return _vector_store
    
    # Load dan split documents
    documents = load_policy_documents()
    splits = split_documents(documents)
    
    # Create embeddings dan vector store
    embeddings = get_embeddings()
    _vector_store = InMemoryVectorStore.from_documents(
        documents=splits,
        embedding=embeddings
    )
    
    print(f"[RAG] Indexed {len(splits)} document chunks")
    
    return _vector_store


def get_policy_retriever(k: int = 4):
    """
    Get retriever untuk search policy documents.
    
    Args:
        k: Number of documents to retrieve (default: 4)
        
    Returns:
        Retriever: VectorStore retriever
    """
    vector_store = initialize_vector_store()
    return vector_store.as_retriever(search_kwargs={"k": k})


def search_policies(query: str, k: int = 4) -> List[Document]:
    """
    Search policy documents dengan query.
    
    Args:
        query: Search query
        k: Number of results
        
    Returns:
        List[Document]: Relevant documents
    """
    vector_store = initialize_vector_store()
    results = vector_store.similarity_search(query, k=k)
    return results


def search_policies_with_score(query: str, k: int = 4) -> List[tuple]:
    """
    Search policy documents dan return dengan similarity score.
    
    Args:
        query: Search query
        k: Number of results
        
    Returns:
        List[tuple]: List of (Document, score) tuples
    """
    vector_store = initialize_vector_store()
    results = vector_store.similarity_search_with_score(query, k=k)
    return results
