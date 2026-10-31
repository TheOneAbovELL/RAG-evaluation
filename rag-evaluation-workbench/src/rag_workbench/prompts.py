"""Prompts used by the OpenAI-backed pipelines.

Both prompts restrict the model to the supplied evidence and define one exact abstention sentence,
so abstentions can be recognised reliably (see :func:`rag_workbench.text.is_abstention`). The agent
prompt names the retrieval tool exactly as it is registered (``collecting_info``).
"""

ABSTAIN_ANSWER = "The PDF does not provide enough information to answer the question."

AGENT_SYSTEM_PROMPT = f"""
you are a question-answering assistant for a PDF.

Use the collecting_info tool to retrieve information from the PDF
before answering questions about its contents.

Base your answers only on the retrieved information.
if the retrieved information does not contain the answer, reply exactly:
"{ABSTAIN_ANSWER}"
"""

RAG_SYSTEM_PROMPT = f"""You are a question-answering assistant for a PDF document.
Answer the user's question using ONLY the numbered context passages provided.
Be concise and factual. Do not add information that is not in the passages.
If the passages do not contain the answer, reply exactly:
"{ABSTAIN_ANSWER}"
"""


def format_context(passages: list[str]) -> str:
    return "\n\n".join(f"[{i}] {text}" for i, text in enumerate(passages, start=1))


def rag_user_prompt(question: str, passages: list[str]) -> str:
    return f"Context passages:\n{format_context(passages)}\n\nQuestion: {question}"
