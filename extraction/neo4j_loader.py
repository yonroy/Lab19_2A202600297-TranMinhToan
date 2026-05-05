import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

from neo4j import GraphDatabase

BASE_DIR   = Path(__file__).parent.parent / "data"
GRAPH_PATH = BASE_DIR / "graph.json"


def _safe_label(label: str) -> str:
    """Normalize label for Cypher: letters, digits, underscore only."""
    value = re.sub(r"[^A-Za-z0-9_]", "_", (label or "Entity").strip())
    if not value:
        value = "Entity"
    if value[0].isdigit():
        value = f"L_{value}"
    return value


def _safe_rel_type(rel_type: str) -> str:
    """Normalize relationship type for Cypher."""
    value = re.sub(r"[^A-Za-z0-9_]", "_", (rel_type or "RELATED_TO").strip().upper())
    if not value:
        value = "RELATED_TO"
    if value[0].isdigit():
        value = f"R_{value}"
    return value


def load_graph(graph_path: Path = GRAPH_PATH) -> dict:
    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)


def upload_to_neo4j(graph: dict):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database=NEO4J_DATABASE) as session:
        # Xóa data cũ
        session.run("MATCH (n) DETACH DELETE n")
        print("🗑️  Đã xóa data cũ")

        # Upload nodes
        nodes = graph.get("nodes", [])
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                continue

            label = _safe_label(node.get("label", "Entity"))
            props = {"id": node["id"], **node.get("properties", {})}
            props["original_label"] = node.get("label", "Entity")
            # Lọc None values
            props = {k: v for k, v in props.items() if v is not None}
            session.run(
                f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                id=node_id, props=props
            )
        print(f"✅ Đã upload {len(nodes)} nodes")

        # Upload relationships
        rels = graph.get("relationships", [])
        for rel in rels:
            from_id = rel.get("from")
            to_id = rel.get("to")
            if not (from_id and to_id):
                continue

            rel_type = _safe_rel_type(rel.get("type"))
            props    = {k: v for k, v in rel.get("properties", {}).items() if v is not None}
            props["original_type"] = rel.get("type", "RELATED_TO")
            session.run(
                f"""
                MATCH (a {{id: $from_id}})
                MATCH (b {{id: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $props
                """,
                from_id=from_id, to_id=to_id, props=props
            )
        print(f"✅ Đã upload {len(rels)} relationships")

    driver.close()
    print("🎉 Done! Graph đã lên Neo4j AuraDB")


if __name__ == "__main__":
    graph = load_graph()
    print(f"📂 Đọc graph: {len(graph['nodes'])} nodes, {len(graph['relationships'])} rels")
    upload_to_neo4j(graph)