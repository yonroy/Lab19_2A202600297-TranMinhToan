import json
import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.embedder import embed_batch
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

BASE_DIR = Path(__file__).parent.parent.parent / "data"
CHUNKS_PATH = BASE_DIR / "chunks.json"


def _norm_company_id(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _create_schema(session, dim: int = 1536):
    session.run(
        "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
        "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT company_id_unique IF NOT EXISTS "
        "FOR (c:Company) REQUIRE c.id IS UNIQUE"
    )
    session.run(
        "CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS "
        "FOR (c:Chunk) ON (c.embedding) "
        "OPTIONS {indexConfig: {"
        f"`vector.dimensions`: {dim}, "
        "`vector.similarity_function`: 'cosine'"
        "}}"
    )


def build_index(chunks_path: Path = CHUNKS_PATH):
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks")

    texts = [c["text"] for c in chunks]
    print("Embedding...")
    embeddings = embed_batch(texts)

    for c, emb in zip(chunks, embeddings):
        c["embedding"] = emb
        c["company_id"] = _norm_company_id(c["company"])

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session(database=NEO4J_DATABASE) as session:
        _create_schema(session, dim=len(embeddings[0]) if embeddings else 1536)
        print("Schema created")

        batch_size = 100
        total_batches = (len(chunks) - 1) // batch_size + 1
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            session.run(
                "UNWIND $rows AS row "
                "MERGE (co:Company {id: row.company_id}) "
                "  ON CREATE SET co.name = row.company "
                "MERGE (ch:Chunk {chunk_id: row.chunk_id}) "
                "SET ch.company    = row.company, "
                "    ch.company_id = row.company_id, "
                "    ch.chunk_index = row.chunk_index, "
                "    ch.word_count = row.word_count, "
                "    ch.text       = row.text, "
                "    ch.embedding  = row.embedding "
                "MERGE (co)-[:HAS_CHUNK]->(ch)",
                rows=batch
            )
            print(f"  Batch {i // batch_size + 1}/{total_batches}")

    driver.close()
    print(f"Done: {len(chunks)} chunks uploaded to Neo4j")


if __name__ == "__main__":
    build_index()
