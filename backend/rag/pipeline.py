"""
RAG pipeline — orchestrates the full ask flow:

  1. Embed the user question (local)
  2. Retrieve top-k chunks from ChromaDB
  3. Guardrail check (similarity threshold)
  4. Build prompt + call Groq
  5. Detect NOT_FOUND_IN_DOCUMENT signal
  6. Compute confidence score
  7. Return structured AskResponse
"""

from __future__ import annotations

import logging

from groq import Groq

from backend.config import (
    GROQ_API_KEY,
    GROQ_QA_MODEL,
    GROQ_MAX_TOKENS,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from backend.retrieval.vector_store import query_chunks
from backend.guardrails.guardrails import check_guardrails
from backend.rag.prompts import build_qa_prompt
from backend.rag.confidence import compute_confidence

logger = logging.getLogger(__name__)

NOT_FOUND_RESPONSE = "Not found in document."
REFUSED_RESPONSE   = "I could not find relevant information in the document to answer this question."


def ask(doc_id: str, question: str) -> dict:
    """
    Full RAG pipeline for a single question.

    Returns:
      {
        "answer":              str,
        "source_chunks":       list[{text, similarity, chunk_id}],
        "confidence_score":    float,
        "confidence_label":    str,
        "guardrail_triggered": bool,
        "guardrail_reason":    str | None,
      }
    """
    # ── 1 & 2. Retrieve chunks (ChromaDB embeds the query internally) ──────────
    hits = query_chunks(doc_id, query_text=question, top_k=TOP_K)

    if not hits:
        return _refused("No chunks found for this document.", [])

    similarities = [h["similarity"] for h in hits]

    # ── 3. Guardrail check ─────────────────────────────────────────────────────
    guardrail = check_guardrails(similarities)
    if not guardrail["passed"]:
        return _refused(guardrail["reason"], hits)

    # ── 4. Build prompt + call Groq ────────────────────────────────────────────
    chunk_texts = [h["text"] for h in hits]
    system_prompt, user_prompt = build_qa_prompt(chunk_texts, question)

    try:
        client   = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_QA_MODEL,
            messages=[
                {"role": "system",  "content": system_prompt},
                {"role": "user",    "content": user_prompt},
            ],
            max_tokens=GROQ_MAX_TOKENS,
            temperature=0.0,   # deterministic — no creativity needed
        )
        raw_answer = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Groq API error: %s", exc)
        raise

    # ── 5. NOT_FOUND signal ────────────────────────────────────────────────────
    if "NOT_FOUND_IN_DOCUMENT" in raw_answer:
        return {
            "answer":              NOT_FOUND_RESPONSE,
            "source_chunks":       _format_hits(hits),
            "confidence_score":    0.0,
            "confidence_label":    "refused",
            "guardrail_triggered": False,
            "guardrail_reason":    None,
        }

    # ── 6. Confidence scoring ──────────────────────────────────────────────────
    score, label = compute_confidence(similarities, raw_answer, chunk_texts)

    return {
        "answer":              raw_answer,
        "source_chunks":       _format_hits(hits),
        "confidence_score":    score,
        "confidence_label":    label,
        "guardrail_triggered": False,
        "guardrail_reason":    None,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _refused(reason: str, hits: list[dict]) -> dict:
    return {
        "answer":              REFUSED_RESPONSE,
        "source_chunks":       _format_hits(hits),
        "confidence_score":    0.0,
        "confidence_label":    "refused",
        "guardrail_triggered": True,
        "guardrail_reason":    reason,
    }


def _format_hits(hits: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id":   h["chunk_id"],
            "text":       h["text"],
            "similarity": h["similarity"],
        }
        for h in hits
    ]
