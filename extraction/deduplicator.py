# deduplicator.py
import json
from pathlib import Path

def deduplicate(all_extractions: list[dict]) -> tuple[dict, list]:
    """
    Gộp tất cả nodes và relationships từ mọi chunk
    - Nodes: merge theo id, cộng dồn properties
    - Relationships: loại bỏ trùng lặp (from, to, type)
    """
    merged_nodes = {}          # id → node dict
    seen_rels    = set()       # (from, to, type) → dedup key
    merged_rels  = []

    for extraction in all_extractions:

        # ── Merge Nodes ──────────────────────────────────
        for node in extraction.get("nodes", []):
            nid = node.get("id", "").strip().lower()
            if not nid:
                continue

            if nid not in merged_nodes:
                merged_nodes[nid] = {
                    "id":         nid,
                    "label":      node.get("label", "Entity"),
                    "properties": node.get("properties", {})
                }
            else:
                # Cập nhật thêm properties còn thiếu (không ghi đè)
                existing_props = merged_nodes[nid]["properties"]
                for key, val in node.get("properties", {}).items():
                    if key not in existing_props or existing_props[key] is None:
                        existing_props[key] = val

        # ── Merge Relationships ──────────────────────────
        for rel in extraction.get("relationships", []):
            from_id  = rel.get("from", "").strip().lower()
            to_id    = rel.get("to",   "").strip().lower()
            rel_type = rel.get("type", "").strip().upper()

            if not (from_id and to_id and rel_type):
                continue

            dedup_key = (from_id, to_id, rel_type)
            if dedup_key not in seen_rels:
                seen_rels.add(dedup_key)
                merged_rels.append({
                    "from":       from_id,
                    "to":         to_id,
                    "type":       rel_type,
                    "properties": rel.get("properties", {})
                })

    print(f"📊 Sau dedup:")
    print(f"   Nodes         : {len(merged_nodes)}")
    print(f"   Relationships : {len(merged_rels)}")

    return merged_nodes, merged_rels


def save_graph(merged_nodes: dict, merged_rels: list, output_path: str | Path):
    """
    Lưu graph (nodes + relationships) ra file JSON
    """
    graph = {
        "nodes":         list(merged_nodes.values()),
        "relationships": merged_rels,
        "stats": {
            "node_count": len(merged_nodes),
            "rel_count":  len(merged_rels),
        }
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"💾 Đã lưu graph → {output_path}")


def load_extractions(extractions_path: str | Path) -> list[dict]:
    """
    Đọc file JSON chứa danh sách extraction (output của llm_extraction_relationship.py)
    """
    with open(extractions_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    base_dir         = Path(__file__).parent.parent / "data"
    extractions_path = base_dir / "extracted_graph.json"
    output_path      = base_dir / "graph.json"

    if not extractions_path.exists():
        print(f"❌ Không tìm thấy: {extractions_path}")
        print("   Hãy chạy extraction/llm_extraction_relationship.py trước.")
        raise SystemExit(1)

    print(f"📂 Đọc extractions từ {extractions_path} ...")
    all_extractions = load_extractions(extractions_path)
    print(f"   → {len(all_extractions)} chunk extractions")

    merged_nodes, merged_rels = deduplicate(all_extractions)
    save_graph(merged_nodes, merged_rels, output_path)
