"""
graph_rag/retriever.py
Query -> top-K chunks (Neo4j vector search) + BFS subgraph expansion
"""
import sys
from collections import deque
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from flat_rag.retriever import retrieve as retrieve_chunks
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

# Cypher: load ALL edges once (id -> id), used for BFS adjacency
_CYPHER_ALL_EDGES = """
MATCH (a)-[r]->(b)
WHERE (a:Company OR a:Chunk OR a.id IS NOT NULL)
  AND (b:Company OR b:Chunk OR b.id IS NOT NULL)
RETURN
  coalesce(a.id, a.chunk_id) AS src,
  coalesce(b.id, b.chunk_id) AS dst,
  type(r) AS rel_type,
  properties(r) AS props,
  labels(a) AS src_labels, properties(a) AS src_props,
  labels(b) AS dst_labels, properties(b) AS dst_props
"""


def _load_graph_from_neo4j(driver) -> tuple[dict, list]:
    """
    Returns:
      adj  : {node_id: [(neighbour_id, rel_dict), ...]}
      edges: [rel_dict, ...]  (full edge list for fast lookup)
    """
    adj: dict[str, list] = {}
    edges: list[dict] = []
    node_meta: dict[str, dict] = {}  # node_id -> {label, properties}

    with driver.session(database=NEO4J_DATABASE) as session:
        rows = session.run(_CYPHER_ALL_EDGES).data()

    for row in rows:
        src = row["src"] or ""
        dst = row["dst"] or ""
        if not src or not dst:
            continue

        # store node metadata
        if src not in node_meta:
            lbs = row["src_labels"] or []
            node_meta[src] = {
                "id": src,
                "label": lbs[0] if lbs else "Entity",
                "properties": row["src_props"] or {},
            }
        if dst not in node_meta:
            lbs = row["dst_labels"] or []
            node_meta[dst] = {
                "id": dst,
                "label": lbs[0] if lbs else "Entity",
                "properties": row["dst_props"] or {},
            }

        edge = {
            "from": src,
            "to": dst,
            "type": row["rel_type"],
            "properties": row["props"] or {},
        }
        edges.append(edge)

        # undirected adjacency for BFS
        adj.setdefault(src, []).append((dst, edge))
        adj.setdefault(dst, []).append((src, edge))

    return adj, edges, node_meta


def _bfs(adj: dict, seeds: list[str], max_hops: int) -> tuple[set, set]:
    """
    BFS from seed nodes up to max_hops.
    Returns (visited_node_ids, visited_edge_keys)
    edge_key = frozenset({from, to}) + type (represented as tuple)
    """
    visited_nodes: set[str] = set()
    visited_edges: set[tuple] = set()

    queue: deque[tuple[str, int]] = deque()
    for seed in seeds:
        if seed:
            queue.append((seed, 0))
            visited_nodes.add(seed)

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbour, edge in adj.get(node_id, []):
            edge_key = (min(edge["from"], edge["to"]),
                        max(edge["from"], edge["to"]),
                        edge["type"])
            visited_edges.add(edge_key)
            if neighbour not in visited_nodes:
                visited_nodes.add(neighbour)
                queue.append((neighbour, depth + 1))

    return visited_nodes, visited_edges


def retrieve_subgraph(query: str, top_k_chunks: int = 5, hop: int = 2) -> dict:
    """
    1. Top-K chunks via Neo4j vector index
    2. Seed BFS from Company nodes found in those chunks
    3. BFS expansion up to `hop` hops across the full graph
    Returns: {chunks, nodes, relationships}
    """
    chunks = retrieve_chunks(query, top_k=top_k_chunks)
    company_ids = sorted({c["company_id"] for c in chunks if c.get("company_id")})

    if not company_ids:
        return {"chunks": chunks, "nodes": [], "relationships": []}

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    adj, all_edges, node_meta = _load_graph_from_neo4j(driver)
    driver.close()

    visited_nodes, visited_edge_keys = _bfs(adj, company_ids, max_hops=hop)

    nodes = [node_meta[nid] for nid in visited_nodes if nid in node_meta]

    relationships = [
        e for e in all_edges
        if (min(e["from"], e["to"]), max(e["from"], e["to"]), e["type"])
        in visited_edge_keys
    ]

    return {
        "chunks": chunks,
        "nodes": nodes,
        "relationships": relationships,
    }


if __name__ == "__main__":
    query = "Who founded OpenAI?"
    result = retrieve_subgraph(query, top_k_chunks=3, hop=2)
    print(f"Chunks : {len(result['chunks'])}")
    print(f"Nodes  : {len(result['nodes'])}")
    print(f"Rels   : {len(result['relationships'])}")
