"""
graph_rag/rag.py
Full Graph RAG pipeline: query → subgraph + chunks → generate
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from graph_rag.retriever import retrieve_subgraph
from shared.llm import call_llm

SYSTEM_PROMPT = """You are a helpful AI assistant with knowledge about AI companies.
You are given:
1. Relevant text chunks from Wikipedia articles
2. A knowledge graph subgraph (entities and relationships)

Use BOTH sources to answer the question accurately.
If the answer is not in the provided context, say "I don't have enough information."
Be concise and factual."""


def build_context(chunks: list[dict], nodes: list[dict], rels: list[dict]) -> str:
    parts = []

    if chunks:
        parts.append("=== TEXT CHUNKS ===")
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] ({c['company']}, score={c['score']})\n{c['text']}")

    _SKIP_PROPS = {"embedding", "text", "chunk_id", "company_id", "chunk_index", "word_count"}
    if nodes:
        parts.append("=== GRAPH NODES ===")
        for n in nodes:
            props = ", ".join(
                f"{k}={v}" for k, v in n.get("properties", {}).items()
                if v and k not in _SKIP_PROPS
            )
            parts.append(f"- [{n.get('label','?')}] {n['id']}  {props}")

    if rels:
        parts.append("=== GRAPH RELATIONSHIPS ===")
        for r in rels:
            props = ", ".join(f"{k}={v}" for k, v in r.get("properties", {}).items() if v)
            line = f"- ({r['from']}) --[{r['type']}]--> ({r['to']})"
            if props:
                line += f"  {props}"
            parts.append(line)

    return "\n\n".join(parts)


def answer(query: str, top_k: int = 5) -> dict:
    """
    Trả về dict gồm:
      - query: câu hỏi gốc
      - answer: câu trả lời từ LLM
      - sources: chunks đã dùng
      - graph_stats: số nodes/rels dùng làm context
    """
    subgraph = retrieve_subgraph(query, top_k_chunks=top_k)
    chunks   = subgraph["chunks"]
    nodes    = subgraph["nodes"]
    rels     = subgraph["relationships"]

    # Exclude Chunk nodes (already in chunks), keep only entity nodes
    entity_nodes = [n for n in nodes if n.get("label") not in ("Chunk", "Company")][:40]
    context     = build_context(chunks, entity_nodes, rels[:80])
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"
    response    = call_llm(SYSTEM_PROMPT, user_prompt)

    return {
        "query":   query,
        "answer":  response,
        "sources": [{"company": c["company"], "chunk_id": c["chunk_id"], "score": c["score"]} for c in chunks],
        "graph_stats": {"nodes": len(nodes), "relationships": len(rels)},
    }


if __name__ == "__main__":
    q = "What products has OpenAI released?"
    result = answer(q, top_k=5)
    print(f"\nQ: {result['query']}")
    print(f"\nA: {result['answer']}")
    print(f"\nGraph context: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['relationships']} rels")
    print(f"\nSources:")
    for s in result["sources"]:
        print(f"  - {s['company']} ({s['chunk_id']})  score={s['score']}")
