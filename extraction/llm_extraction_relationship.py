# extractor.py
import os
import json
import time
import re
from openai import OpenAI
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────────────────────────
#  PROMPT — chỉnh tại đây để thay đổi schema
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a knowledge graph extraction engine.
Your job: read text about a company and extract structured entities and relationships.
Return ONLY valid JSON. No explanation. No markdown fences.
"""

def build_user_prompt(company: str, chunk_text: str) -> str:
    return f"""
This text is from a Wikipedia article about: "{company}"

=== NODE TYPES ===
- Company    : name, founded_year, headquarters, country, industry, employee_count
- Person     : name, role, nationality
- Product    : name, release_year, type, description
- Technology : name, type
- Organization: name, type, country
- Location   : name, country

=== RELATIONSHIP TYPES ===
Company → Person       : FOUNDED_BY, CEO_OF, FORMER_CEO_OF, EMPLOYED_BY
Company → Company      : ACQUIRED, INVESTED_IN, COMPETES_WITH, SPUN_OFF_FROM, PARTNER_OF
Company → Product      : DEVELOPED, OWNS
Company → Technology   : USES, DEVELOPED
Company → Organization : MEMBER_OF, LISTED_ON, PARTNER_OF, PROVIDED_SERVICE_TO
Company → Location     : HEADQUARTERED_IN, BASED_IN
Person  → Company      : FOUNDED, WORKS_AT, INVESTED_IN

=== RULES ===
1. Only extract facts EXPLICITLY stated in the text — no inference
2. Normalize entity IDs: lowercase, underscores, no spaces
   Example: "Google DeepMind" → id: "google_deepmind"
3. For the main company "{company}", always use id: "{company.lower().replace(' ', '_')}"
4. Relationship properties are optional — only add if clearly stated
5. Skip duplicates within this chunk

=== OUTPUT FORMAT (strict JSON) ===
{{
  "nodes": [
    {{
      "id": "accenture",
      "label": "Company",
      "properties": {{
        "name": "Accenture",
        "founded_year": 1989,
        "headquarters": "Dublin",
        "country": "Ireland"
      }}
    }}
  ],
  "relationships": [
    {{
      "from": "julie_sweet",
      "to": "accenture",
      "type": "CEO_OF",
      "properties": {{
        "since": 2019
      }}
    }}
  ]
}}

=== TEXT TO ANALYZE ===
{chunk_text}
"""


def extract_from_chunk(chunk: dict) -> dict:
    """
    Gửi 1 chunk lên Claude, nhận về nodes + relationships
    Trả về dict với kết quả và metadata chi phí
    """
    start = time.time()

    try:
        response = client.chat.completions.create(
            model      = "gpt-4o-mini",
            max_tokens = 2000,
            messages   = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(chunk["company"], chunk["text"])}
            ]
        )

        elapsed   = time.time() - start
        raw_text  = response.choices[0].message.content
        parsed    = _safe_parse_json(raw_text)

        return {
            "chunk_id":     chunk["chunk_id"],
            "company":      chunk["company"],
            "nodes":        parsed.get("nodes", []),
            "relationships": parsed.get("relationships", []),
            "meta": {
                "tokens_in":  response.usage.prompt_tokens,
                "tokens_out": response.usage.completion_tokens,
                "time_s":     round(elapsed, 2),
                "cost_usd":   _calc_cost(response.usage)
            }
        }

    except Exception as e:
        print(f"  ❌ Lỗi chunk {chunk['chunk_id']}: {e}")
        return {
            "chunk_id": chunk["chunk_id"],
            "company":  chunk["company"],
            "nodes": [], "relationships": [],
            "meta": {"error": str(e)}
        }


def _safe_parse_json(text: str) -> dict:
    """Parse JSON an toàn — xử lý cả trường hợp Claude thêm ```json```"""
    # Thử parse thẳng
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tìm JSON block trong text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Trả về rỗng nếu thất bại hoàn toàn
    print(f"  ⚠️  Không parse được JSON, bỏ qua chunk này")
    return {"nodes": [], "relationships": []}


def _calc_cost(usage) -> float:
    """GPT-4o mini pricing (USD per token)"""
    cost_in  = usage.prompt_tokens     * 0.00000015  # $0.15 / 1M tokens
    cost_out = usage.completion_tokens * 0.0000006   # $0.60 / 1M tokens
    return round(cost_in + cost_out, 6)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    base_dir    = Path(__file__).parent.parent / "data"
    chunks_path = base_dir / "chunks.json"
    output_path = base_dir / "extracted_graph.json"

    if not chunks_path.exists():
        print(f"❌ Không tìm thấy {chunks_path}")
        print("   Hãy chạy extraction/entity_extractor.py trước.")
        sys.exit(1)

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Giới hạn số chunk để tránh tốn token (bỏ [:N] để chạy toàn bộ)
    MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", len(chunks)))
    chunks = chunks[:MAX_CHUNKS]

    print(f"🚀 Bắt đầu extraction: {len(chunks)} chunks")

    results = []
    total_cost = 0.0

    for i, chunk in enumerate(chunks):
        print(f"  [{i+1}/{len(chunks)}] {chunk['company']} (chunk {chunk['chunk_index']})")
        result = extract_from_chunk(chunk)
        results.append(result)
        cost = result["meta"].get("cost_usd", 0)
        total_cost += cost

        # Rate limit: tránh 429
        time.sleep(0.5)

    # Lưu kết quả
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_nodes = sum(len(r["nodes"]) for r in results)
    total_rels  = sum(len(r["relationships"]) for r in results)

    print(f"\n✅ Hoàn thành!")
    print(f"   Nodes        : {total_nodes}")
    print(f"   Relationships: {total_rels}")
    print(f"   Chi phí ước tính: ${total_cost:.4f} USD")
    print(f"   Kết quả lưu tại: {output_path}")
