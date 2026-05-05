import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from flat_rag.retriever import retrieve as retrieve_chunks
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE


def retrieve_subgraph(query: str, top_k_chunks: int = 5, hop: int = 2) -> dict:
    chunks = retrieve_chunks(query, top_k=top_k_chunks)
    company_ids = sorted({c["company_id"] for c in chunks if c.get("company_id")})

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )

    cypher_nodes = f"""
    UNWIND $company_ids AS cid
    MATCH (c:Company {{id: cid}})
    MATCH p = (c)-[*1..{hop}]-(n)
    UNWIND nodes(p) AS x
    RETURN DISTINCT labels(x) AS labels, properties(x) AS props
    """

    cypher_rels = f"""
    UNWIND $company_ids AS cid
    MATCH (c:Company {{id: cid}})
    MATCH p = (c)-[*1..{hop}]-(n)
    UNWIND relationships(p) AS r
    RETURN DISTINCT
      properties(r) AS props,
      type(r) AS rel_type,
      properties(startNode(r)) AS start_props,
      properties(endNode(r)) AS end_props
    """

    with driver.session(database=NEO4J_DATABASE) as session:
        raw_nodes = session.run(cypher_nodes, company_ids=company_ids).data()
        raw_rels = session.run(cypher_rels, company_ids=company_ids).data()

    driver.close()

    nodes = []
    for row in raw_nodes:
        labels = row["labels"] or []
        props = row["props"] or {}
        nodes.append({
            "id": props.get("id", props.get("chunk_id", "")),
            "label": labels[0] if labels else "Entity",
            "properties": props
        })

    relationships = []
    for row in raw_rels:
        sp = row["start_props"] or {}
        ep = row["end_props"] or {}
        relationships.append({
            "from": sp.get("id", sp.get("chunk_id", "")),
            "to": ep.get("id", ep.get("chunk_id", "")),
            "type": row["rel_type"],
            "properties": row["props"] or {}
        })

    return {
        "chunks": chunks,
        "nodes": nodes,
        "relationships": relationships
    }


if __name__ == "__main__":
    result = retrieve_subgraph("Who founded OpenAI?", top_k_chunks=3, hop=2)
    print(len(result["chunks"]), len(result["nodes"]), len(result["relationships"]))