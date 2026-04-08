"""
Composite confidence scoring (0.0 – 1.0).

Three signals, weighted:
  1. Retrieval score  (50%) — average cosine similarity of retrieved chunks.
     High similarity = the document contains content closely related to the question.

  2. Coverage score   (30%) — fraction of answer words that appear in retrieved context.
     Low coverage = LLM introduced terms not present in the source → hallucination risk.

  3. Validity score   (20%) — penalises refusal answers and suspiciously short responses.

Final label:
  >= 0.75  → "high"
  >= 0.50  → "medium"
  >= 0.30  → "low"
  <  0.30  → "refused"
"""

from __future__ import annotations

import re
from backend.config import W_RETRIEVAL, W_COVERAGE, W_VALIDITY

NOT_FOUND_SIGNAL = "not_found_in_document"

# Common stop-words excluded from coverage check to avoid false inflation
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "it", "its",
    "in", "on", "at", "to", "of", "for", "and", "or", "with",
    "this", "that", "be", "been", "by", "as", "from", "has",
}


def compute_confidence(
    similarities: list[float],
    answer: str,
    context_chunks: list[str],
) -> tuple[float, str]:
    """
    Returns (score: float, label: str).
    """
    answer_lower = answer.strip().lower()

    # Hard zero for explicit not-found responses
    if NOT_FOUND_SIGNAL in answer_lower.replace(" ", "_"):
        return 0.0, "refused"

    # ── Signal 1: retrieval score ──────────────────────────────────────────────
    retrieval_score = sum(similarities) / len(similarities) if similarities else 0.0

    # ── Signal 2: coverage score ───────────────────────────────────────────────
    answer_words  = _tokenise(answer_lower) - _STOPWORDS
    context_words = _tokenise(" ".join(context_chunks).lower()) - _STOPWORDS

    if answer_words:
        overlap        = answer_words & context_words
        coverage_score = len(overlap) / len(answer_words)
    else:
        coverage_score = 0.0

    # ── Signal 3: validity score ───────────────────────────────────────────────
    if len(answer.strip()) < 10:
        validity_score = 0.2
    elif any(p in answer_lower for p in ("not found", "not in document", "cannot find")):
        validity_score = 0.1
    else:
        validity_score = 1.0

    # ── Composite ──────────────────────────────────────────────────────────────
    score = (
        W_RETRIEVAL * retrieval_score
        + W_COVERAGE  * coverage_score
        + W_VALIDITY  * validity_score
    )
    score = round(min(max(score, 0.0), 1.0), 3)

    if score >= 0.75:
        label = "high"
    elif score >= 0.50:
        label = "medium"
    elif score >= 0.30:
        label = "low"
    else:
        label = "refused"

    return score, label


def _tokenise(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text))
