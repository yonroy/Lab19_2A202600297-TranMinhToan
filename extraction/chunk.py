import os
import json
from pathlib import Path

def load_and_chunk_all_files(articles_dir, min_words=30, max_words=600):
    """
    Đọc tất cả .txt, chunk theo đoạn văn (paragraph), gắn metadata công ty
    """
    all_chunks = []
    article_files = list(Path(articles_dir).glob("*.txt"))

    print(f"📁 Tìm thấy {len(article_files)} files")

    for file_path in article_files:
        company_name = file_path.stem.replace("_", " ")
        # "Google_DeepMind.txt" → "Google DeepMind"

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        chunks = chunk_single_file(text, company_name, min_words, max_words)
        all_chunks.extend(chunks)

        print(f"  ✅ {company_name}: {len(chunks)} chunks")

    return all_chunks


def chunk_single_file(text, company_name, min_words=30, max_words=600):
    """
    Chunk theo đoạn văn (split theo dòng trống).
    - Bỏ đoạn quá ngắn (< min_words từ).
    - Gộp các đoạn liên tiếp nếu tổng < max_words, cắt nếu 1 đoạn vượt max_words.
    """
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Gộp đoạn ngắn với đoạn liền sau
    merged = []
    buffer = ""
    for para in raw_paragraphs:
        combined = (buffer + " " + para).strip() if buffer else para
        if len(combined.split()) <= max_words:
            buffer = combined
        else:
            if buffer:
                merged.append(buffer)
            # Nếu 1 đoạn đơn lẻ vượt max_words → cắt theo từ
            if len(para.split()) > max_words:
                words = para.split()
                for j in range(0, len(words), max_words):
                    merged.append(" ".join(words[j:j + max_words]))
            else:
                buffer = para
    if buffer:
        merged.append(buffer)

    chunks = []
    i = 0
    for para in merged:
        word_count = len(para.split())
        if word_count < min_words:
            continue
        chunks.append({
            "company":     company_name,
            "chunk_id":    f"{company_name}_{i}",
            "chunk_index": i,
            "text":        para,
            "word_count":  word_count,
        })
        i += 1

    return chunks


def save_chunks(chunks, output_path):
    """
    Lưu toàn bộ chunks ra file JSON
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Đã lưu {len(chunks)} chunks → {output_path}")


def print_stats(chunks):
    """
    In thống kê tổng quan về corpus
    """
    companies = {}
    for chunk in chunks:
        c = chunk["company"]
        companies[c] = companies.get(c, 0) + 1

    print(f"\n📊 Thống kê:")
    print(f"  - Tổng số chunks : {len(chunks)}")
    print(f"  - Số công ty     : {len(companies)}")
    avg = len(chunks) / len(companies) if companies else 0
    print(f"  - Trung bình     : {avg:.1f} chunks/công ty")


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent / "data"
    articles_dir = base_dir / "articles"
    output_path  = base_dir / "chunks.json"

    if not articles_dir.exists():
        print(f"❌ Không tìm thấy thư mục: {articles_dir}")
        print("   Hãy chạy data/extract.py trước.")
        raise SystemExit(1)

    all_chunks = load_and_chunk_all_files(articles_dir, min_words=30, max_words=600)
    save_chunks(all_chunks, output_path)
    print_stats(all_chunks)
