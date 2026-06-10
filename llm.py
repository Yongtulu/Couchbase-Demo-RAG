# llm.py — build the RAG prompt and call the LLM

from ollama_client import generate_answer

SYSTEM = (
    "You are a helpful assistant that answers questions strictly based on "
    "the provided context excerpts from the Couchbase official documentation. "
    "If the answer is not in the context, say so clearly. Be concise and accurate."
)


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[{i+1}] Source: {c['source_title']}\n{c['text']}"
        for i, c in enumerate(chunks)
    )
    return (
        f"{SYSTEM}\n\n"
        f"=== Context ===\n{context}\n\n"
        f"=== Question ===\n{question}\n\n"
        f"=== Answer ===\n"
    )


def ask(question: str, chunks: list[dict]) -> tuple[str, str]:
    """Return (answer, prompt)."""
    prompt = build_prompt(question, chunks)
    answer = generate_answer(prompt)
    return answer, prompt
