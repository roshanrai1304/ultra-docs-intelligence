"""
All LLM prompt templates.

Keeping prompts in one file makes them easy to review, version, and tune
without touching pipeline logic.
"""

QA_SYSTEM = """\
You are a logistics document assistant for a Transportation Management System (TMS).

Rules:
1. Answer ONLY using the provided CONTEXT below.
2. Do NOT use any outside knowledge or make assumptions.
3. If the answer is not present in the CONTEXT, respond with exactly the string: NOT_FOUND_IN_DOCUMENT
4. Be concise and precise. Quote specific values (dates, amounts, names) directly from the context.
5. Never invent, paraphrase beyond what is written, or guess.
"""

QA_USER = """\
CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def build_qa_prompt(chunks: list[str], question: str) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) ready for the Groq chat API.
    """
    context = "\n---\n".join(chunks)
    return QA_SYSTEM, QA_USER.format(context=context, question=question)
