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
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever


# Paths
POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"
CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
COLLECTION_NAME = "compliance_policies"

# Global vector store instance (singleton pattern)
_vector_store: Optional[Chroma] = None
_embeddings: Optional[HuggingFaceEndpointEmbeddings] = None


def get_embeddings() -> HuggingFaceEndpointEmbeddings:
    """
    Get or create HuggingFace embeddings via remote Inference API.
    
    Uses sentence-transformers/all-MiniLM-L6-v2 via HF Inference API.
    No local model download required — HUGGINGFACEHUB_API_TOKEN from .env.
    """
    global _embeddings
    
    if _embeddings is None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        _embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            task="feature-extraction",
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


def initialize_vector_store(force_reload: bool = False) -> Chroma:
    """
    Initialize persistent Chroma vector store.
    
    Data disimpan di data/chroma_db/ dan load otomatis saat restart.
    
    Args:
        force_reload: Jika True, hapus collection dan re-index ulang
        
    Returns:
        Chroma: Persistent vector store
    """
    global _vector_store
    
    if _vector_store is not None and not force_reload:
        return _vector_store
    
    # Hapus collection lama jika force_reload
    if force_reload:
        import shutil
        if CHROMA_PATH.exists():
            shutil.rmtree(CHROMA_PATH)
            print("[RAG] Menghapus ChromaDB cache (force reload)")
    
    embeddings = get_embeddings()
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    
    # Jika sudah ada data persistent, load dari disk (tidak re-embed)
    if not force_reload and any(CHROMA_PATH.iterdir()):
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_PATH),
        )
        count = _vector_store._collection.count()
        print(f"[RAG] Loaded {count} chunks from persistent store")
        return _vector_store
    
    # Index dari awal
    documents = load_policy_documents()
    splits = split_documents(documents)
    
    _vector_store = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_PATH),
    )
    
    print(f"[RAG] Indexed {len(splits)} document chunks to persistent store")
    
    return _vector_store


def get_policy_retriever(k: int = 4) -> "VectorStoreRetriever":
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


def search_policies_with_score(query: str, k: int = 4) -> List[tuple[Document, float]]:
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
