"""
Ultra Doc-Intelligence — FastAPI backend

Endpoints:
  POST /upload   — upload a logistics document; parse, chunk, embed, store
  POST /ask      — ask a question via RAG; returns answer + sources + confidence
  POST /extract  — extract structured shipment fields as JSON
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import ALLOWED_EXTENSIONS, UPLOAD_DIR
from backend.ingestion.parser import parse_document
from backend.ingestion.chunker import chunk_text
from backend.retrieval.embedder import embed_texts, get_embedder
from backend.retrieval.vector_store import store_chunks, collection_exists
from backend.rag.pipeline import ask as rag_ask
from backend.extraction.extractor import extract_fields

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Ultra Doc-Intelligence",
    description="RAG-based logistics document Q&A — powered by Groq + ChromaDB",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    Pre-load the embedding model in a thread so the event loop stays free.
    Model download (~90 MB on first run) can take 30-120 s depending on
    connection speed — running in executor prevents uvicorn from timing out.
    """
    logger.info("Pre-loading embedding model (may download on first run)...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_embedder)
    logger.info("Embedding model ready. Backend accepting requests.")


# ── Request / Response models ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    doc_id:   str
    question: str


class ExtractRequest(BaseModel):
    doc_id: str


class SourceChunk(BaseModel):
    chunk_id:   str
    text:       str
    similarity: float


class AskResponse(BaseModel):
    answer:              str
    source_chunks:       list[SourceChunk]
    confidence_score:    float
    confidence_label:    str           # "high" | "medium" | "low" | "refused"
    guardrail_triggered: bool
    guardrail_reason:    str | None


class UploadResponse(BaseModel):
    doc_id:      str
    filename:    str
    chunk_count: int
    page_count:  int
    doc_type:    str
    status:      str


# ── POST /upload ───────────────────────────────────────────────────────────────

@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a logistics document (PDF, DOCX, TXT).
    Parses, chunks, embeds, and stores it in ChromaDB.
    Returns a doc_id to use in subsequent /ask and /extract calls.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Generate a unique ID for this document
    doc_id   = str(uuid.uuid4())
    doc_dir  = UPLOAD_DIR / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    filepath = doc_dir / file.filename

    # Save file to disk
    contents = await file.read()
    filepath.write_bytes(contents)
    logger.info("Saved upload: %s → %s", file.filename, filepath)

    # Parse
    try:
        parsed = parse_document(filepath)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Chunk
    chunks = chunk_text(parsed["raw_text"], doc_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document produced no usable text chunks.",
        )

    # Embed
    texts      = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    # Store in ChromaDB
    store_chunks(doc_id, chunks, embeddings)

    # Persist the raw text alongside the file (used by /extract)
    (doc_dir / "raw_text.txt").write_text(parsed["raw_text"], encoding="utf-8")

    return UploadResponse(
        doc_id      = doc_id,
        filename    = file.filename,
        chunk_count = len(chunks),
        page_count  = parsed["page_count"],
        doc_type    = parsed["doc_type"],
        status      = "ready",
    )


# ── POST /ask ──────────────────────────────────────────────────────────────────

@app.post("/ask", response_model=AskResponse)
async def ask_question(body: AskRequest):
    """
    Ask a natural-language question about an uploaded document.
    Returns the answer, supporting source chunks, and a confidence score.
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must not be empty.",
        )

    if not collection_exists(body.doc_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{body.doc_id}' not found. Please upload it first.",
        )

    try:
        result = rag_ask(body.doc_id, body.question)
    except Exception as exc:
        logger.error("RAG pipeline error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {exc}",
        )

    return AskResponse(**result)


# ── POST /extract ──────────────────────────────────────────────────────────────

@app.post("/extract")
async def extract(body: ExtractRequest):
    """
    Extract structured shipment fields from the full document text.
    Returns a JSON object with nulls for any fields not found.
    """
    raw_text_path = UPLOAD_DIR / body.doc_id / "raw_text.txt"

    if not raw_text_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{body.doc_id}' not found. Please upload it first.",
        )

    full_text = raw_text_path.read_text(encoding="utf-8")

    try:
        result = extract_fields(full_text)
    except Exception as exc:
        logger.error("Extraction error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {exc}",
        )

    return result


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
