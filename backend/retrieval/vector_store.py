"""
ChromaDB vector store — one collection per uploaded document.

Uses ChromaDB's built-in DefaultEmbeddingFunction (ONNX, all-MiniLM-L6-v2)
so embedding and storage are handled together. Documents are passed as text;
ChromaDB computes and stores the embeddings internally.
"""

from __future__ import annotations

import logging

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from backend.config import CHROMA_DIR, TOP_K

logger = logging.getLogger(__name__)

_client: chromadb.PersistentClient | None = None
_ef = DefaultEmbeddingFunction()


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def store_chunks(doc_id: str, chunks: list[dict], embeddings: list = None) -> None:
    """
    Store chunks in a per-document ChromaDB collection.
    Embeddings are computed by ChromaDB's built-in embedding function.
    The `embeddings` param is kept for API compatibility but ignored.
    """
    client = _get_client()

    try:
        client.delete_collection(name=doc_id)
    except Exception:
        pass

    collection = client.create_collection(
        name=doc_id,
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids       = [c["chunk_id"] for c in chunks],
        documents = [c["text"]     for c in chunks],
        metadatas = [
            {
                "doc_id":     c["doc_id"],
                "char_start": c["char_start"],
                "char_end":   c["char_end"],
            }
            for c in chunks
        ],
    )
    logger.info("Stored %d chunks for doc_id=%s", len(chunks), doc_id)


def query_chunks(doc_id: str, query_embedding: list = None, top_k: int = TOP_K,
                 query_text: str = None) -> list[dict]:
    """
    Retrieve top-k most similar chunks.
    Accepts either query_text (preferred) or query_embedding (ignored, kept for API compat).
    """
    client = _get_client()

    try:
        collection = client.get_collection(name=doc_id, embedding_function=_ef)
    except Exception:
        raise ValueError(f"No document found with doc_id='{doc_id}'. Upload it first.")

    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[query_text or ""],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for i, doc in enumerate(results["documents"][0]):
        distance   = results["distances"][0][i]
        similarity = max(0.0, 1.0 - distance)
        hits.append({
            "chunk_id":   results["ids"][0][i],
            "text":       doc,
            "similarity": round(similarity, 4),
            "metadata":   results["metadatas"][0][i],
        })

    return hits


def collection_exists(doc_id: str) -> bool:
    client = _get_client()
    try:
        client.get_collection(name=doc_id, embedding_function=_ef)
        return True
    except Exception:
        return False
