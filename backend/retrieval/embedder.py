"""
Thin wrapper kept for API compatibility.

Actual embedding is now handled inside ChromaDB's DefaultEmbeddingFunction
(ONNX, all-MiniLM-L6-v2) within vector_store.py.

embed_query() is still called by the RAG pipeline but we now pass the raw
query text through to vector_store.query_chunks() instead of a vector,
so these functions are lightweight pass-throughs.
"""

from __future__ import annotations


def get_embedder():
    """No-op — embedding handled by ChromaDB internally."""
    return None


def embed_texts(texts: list[str]) -> list:
    """No-op — kept for upload pipeline compatibility."""
    return [None] * len(texts)


def embed_query(query: str) -> str:
    """Returns the raw query text; vector_store passes it to ChromaDB."""
    return query
