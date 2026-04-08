"""
Guardrail checks applied before calling the Groq API.

Blocking here (before the LLM call) saves API quota and gives the user
an explicit, honest explanation rather than a low-quality answer.

Current guardrails:
  1. Similarity threshold — refuse if the best retrieved chunk is below
     SIMILARITY_THRESHOLD (cosine similarity). This means the document
     simply does not contain content related to the question.
"""

from backend.config import SIMILARITY_THRESHOLD


def check_guardrails(similarities: list[float]) -> dict:
    """
    Evaluate retrieval similarity scores against configured thresholds.

    Args:
        similarities: cosine similarity scores for the top-k retrieved chunks.

    Returns:
        {
          "passed": bool,
          "reason": str | None   # human-readable explanation if not passed
        }
    """
    if not similarities:
        return {
            "passed": False,
            "reason": "No chunks were retrieved from the document.",
        }

    max_sim = max(similarities)

    if max_sim < SIMILARITY_THRESHOLD:
        return {
            "passed": False,
            "reason": (
                f"The question does not appear to be answerable from this document "
                f"(best retrieval similarity: {max_sim:.2f}, threshold: {SIMILARITY_THRESHOLD:.2f})."
            ),
        }

    return {"passed": True, "reason": None}
