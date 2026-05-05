import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.embedder import embed_text
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    q_vec = embed_text(query)

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    cypher = """
    CALL db.index.vector.queryNodes('chunk_embedding_index', $k, $q)
    YIELD node, score
    RETURN
      node.chunk_id AS chunk_id,
      node.company AS company,
      node.company_id AS company_id,
      node.chunk_index AS chunk_index,
      node.word_count AS word_count,
      node.text AS text,
      score
    ORDER BY score DESC
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        rows = session.run(cypher, k=top_k, q=q_vec).data()

    driver.close()

    results = []
    for r in rows:
        results.append({
            "chunk_id": r["chunk_id"],
            "company": r["company"],
            "company_id": r["company_id"],
            "chunk_index": r["chunk_index"],
            "word_count": r["word_count"],
            "text": r["text"],
            "score": round(float(r["score"]), 4),
        })
    return results


if __name__ == "__main__":
    out = retrieve("Who founded OpenAI?", top_k=3)
    for i, x in enumerate(out, 1):
        print(f"[{i}] {x['company']} score={x['score']}")