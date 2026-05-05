"""
graph_rag/rag.py
Full Graph RAG pipeline: query → subgraph + chunks → generate
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from graph_rag.retriever import retrieve_subgraph
from shared.llm import call_llm_with_usage

SYSTEM_PROMPT = """You are a helpful AI assistant with knowledge about AI companies.
You are given:
1. Relevant text chunks from Wikipedia articles
2. A knowledge graph subgraph (entities and relationships)

Use BOTH sources to answer the question accurately.
If the answer is not in the provided context, say "I don't have enough information."
Be concise and factual."""


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _node_display_name(node: dict) -> str:
    props = node.get("properties", {}) or {}
    for key in ("name", "title", "company", "org_name"):
        if props.get(key):
            return _safe_text(props[key])
    return _safe_text(node.get("id", "Unknown"))


def _format_props(props: dict, skip: set[str] | None = None, limit: int = 6) -> str:
    if not props:
        return ""
    skip = skip or set()
    pairs = []
    for key, value in props.items():
        if key in skip:
            continue
        text = _safe_text(value)
        if not text:
            continue
        pairs.append(f"{key}={text}")
        if len(pairs) >= limit:
            break
    return "; ".join(pairs)


def format_graph_context(nodes: list[dict], relationships: list[dict]) -> str:
    """Format graph data into readable fact-style context for prompting."""
    parts = []

    if nodes:
        parts.append("=== GRAPH NODE FACTS ===")
        skip = {"embedding", "text", "chunk_id", "company_id", "chunk_index", "word_count"}
        for node in nodes:
            label = _safe_text(node.get("label", "Entity")) or "Entity"
            name = _node_display_name(node)
            details = _format_props(node.get("properties", {}), skip=skip)
            if details:
                parts.append(f"- [{label}] {name}: {details}.")
            else:
                parts.append(f"- [{label}] {name}.")

    if relationships:
        parts.append("=== GRAPH RELATION FACTS ===")
        node_name_by_id = {node.get("id"): _node_display_name(node) for node in nodes}
        for rel in relationships:
            src_id = rel.get("from", "")
            dst_id = rel.get("to", "")
            src = node_name_by_id.get(src_id, _safe_text(src_id) or "Unknown")
            dst = node_name_by_id.get(dst_id, _safe_text(dst_id) or "Unknown")
            rel_type = _safe_text(rel.get("type", "RELATED_TO")).replace("_", " ").lower()
            details = _format_props(rel.get("properties", {}), limit=4)

            line = f"- {src} co quan he {rel_type} voi {dst}"
            if details:
                line += f" ({details})"
            line += "."
            parts.append(line)

    return "\n".join(parts)


def build_context(chunks: list[dict], nodes: list[dict], rels: list[dict]) -> str:
    parts = []

    if chunks:
        parts.append("=== TEXT CHUNKS ===")
        for i, c in enumerate(chunks, 1):
            parts.append(f"[{i}] ({c['company']}, score={c['score']})\n{c['text']}")

    graph_context = format_graph_context(nodes, rels)
    if graph_context:
        parts.append(graph_context)

    return "\n\n".join(parts)


def answer(query: str, top_k: int = 5, hop: int = 2) -> dict:
    """
    Trả về dict gồm:
      - query: câu hỏi gốc
      - answer: câu trả lời từ LLM
      - sources: chunks đã dùng
      - graph_stats: số nodes/rels dùng làm context
    """
    subgraph = retrieve_subgraph(query, top_k_chunks=top_k, hop=hop)
    chunks   = subgraph["chunks"]
    nodes    = subgraph["nodes"]
    rels     = subgraph["relationships"]

    # Exclude Chunk nodes (already in chunks), keep only entity nodes
    entity_nodes = [n for n in nodes if n.get("label") not in ("Chunk", "Company")][:40]
    context     = build_context(chunks, entity_nodes, rels[:80])
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"
    llm_result  = call_llm_with_usage(SYSTEM_PROMPT, user_prompt)

    return {
        "query":   query,
        "answer":  llm_result["answer"],
        "tokens_used": llm_result["tokens_used"],
        "prompt_tokens": llm_result["prompt_tokens"],
        "completion_tokens": llm_result["completion_tokens"],
        "model": llm_result["model"],
        "sources": [{"company": c["company"], "chunk_id": c["chunk_id"], "score": c["score"]} for c in chunks],
        "graph_stats": {"nodes": len(nodes), "relationships": len(rels)},
    }


if __name__ == "__main__":
    q = "What products has OpenAI released?"
    result = answer(q, top_k=5)
    print(f"\nQ: {result['query']}")
    print(f"\nA: {result['answer']}")
    print(f"\nTokens: {result['tokens_used']}")
    print(f"\nGraph context: {result['graph_stats']['nodes']} nodes, {result['graph_stats']['relationships']} rels")
    print(f"\nSources:")
    for s in result["sources"]:
        print(f"  - {s['company']} ({s['chunk_id']})  score={s['score']}")
