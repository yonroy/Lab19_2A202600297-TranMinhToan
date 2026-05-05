"""
flat_rag/rag.py
Flat RAG pipeline: query -> retrieve chunks -> generate answer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from flat_rag.retriever import retrieve as retrieve_chunks
from shared.llm import call_llm_with_usage

SYSTEM_PROMPT = """You are a helpful AI assistant with knowledge about AI companies.
You are given relevant text chunks from Wikipedia-like articles.
Use only the provided context to answer the question.
If the answer is not in the context, say \"I don't have enough information.\"
Be concise and factual."""


def build_context(chunks: list[dict]) -> str:
    parts = ["=== TEXT CHUNKS ==="]
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] ({c['company']}, score={c['score']})\\n{c['text']}")
    return "\\n\\n".join(parts)


def answer(query: str, top_k: int = 5) -> dict:
    chunks = retrieve_chunks(query, top_k=top_k)
    context = build_context(chunks)
    user_prompt = f"Context:\\n{context}\\n\\nQuestion: {query}"
    llm_result = call_llm_with_usage(SYSTEM_PROMPT, user_prompt)

    return {
        "query": query,
        "answer": llm_result["answer"],
        "tokens_used": llm_result["tokens_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
        "model": llm_result["model"],
        "sources": [
            {"company": c["company"], "chunk_id": c["chunk_id"], "score": c["score"]}
            for c in chunks
        ],
    }


if __name__ == "__main__":
    q = "OpenAI được thành lập năm nào?"
    result = answer(q, top_k=5)
    print(f"\\nQ: {result['query']}")
    print(f"\\nA: {result['answer']}")
    print(f"\\nTokens: {result['tokens_used']}")
    print("\\nSources:")
    for s in result["sources"]:
        print(f"  - {s['company']} ({s['chunk_id']})  score={s['score']}")