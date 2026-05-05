# Benchmark Report: Flat RAG vs Graph RAG

## Pham vi
- So cau hoi: 20
- Nguon du lieu: `benchmark/result.json` va `benchmark/question.json`
- Nhom cau hoi: single-hop, multi-hop, comparison, aggregation (moi nhom 5 cau)
- Accuracy duoc cham tu dong bang LLM-as-judge dua tren `reference_answer` trong `question.json`.

## So sanh nhanh: Accuracy, Latency, Cost

Ket qua tong quan moi:

- Flat RAG: Accuracy 0.525, Latency 3.897s, Cost 3307.80 tokens/cau
- Graph RAG: Accuracy 0.575, Latency 7.037s, Cost 7009.80 tokens/cau

| Chi so | Flat RAG | Graph RAG | Ket luan |
|---|---:|---:|---|
| Accuracy (correctness trung binh, 0-1) | 0.525 | 0.575 | Graph RAG nhinh hon 0.05 |
| Latency (avg time/question) | 3.897s | 7.037s | Flat RAG nhanh hon ~1.81x |
| Cost (avg tokens/question) | 3307.80 | 7009.80 | Flat RAG re hon theo token, Graph RAG ton ~2.12x token |

## Dien giai cho Accuracy

- Mỗi cau tra loi duoc cham diem correctness trong [0,1] boi LLM-as-judge, dua tren:
  - Question
  - Reference answer
  - Candidate answer
- Ket qua trung binh toan bo 20 cau:
  - Flat RAG: 0.525
  - Graph RAG: 0.575

## Dien giai cho Latency

- Latency duoc do bang `time_seconds` moi cau hoi.
- Trung binh toan tap:
	- Flat RAG: 3.897s/cau
	- Graph RAG: 7.037s/cau
- Ket luan: Flat RAG phan hoi nhanh hon ro rang.

## Dien giai cho Cost

- Cost duoc xap xi theo `tokens_used` (vi cung mot model thi token cao hon tuong ung chi phi cao hon).
- Trung binh toan tap:
	- Flat RAG: 3307.80 token/cau
	- Graph RAG: 7009.80 token/cau
- Ket luan: Graph RAG dang ton token gan gap doi.

## Theo tung loai cau hoi (Accuracy, Latency, Cost)

| Loai cau hoi | Flat accuracy | Graph accuracy | Flat avg time (s) | Graph avg time (s) | Flat avg token | Graph avg token |
|---|---:|---:|---:|---:|---:|---:|
| single-hop | 1.00 | 1.00 | 4.185 | 6.086 | 3419.2 | 7142.2 |
| multi-hop | 0.40 | 0.60 | 2.063 | 5.717 | 3323.6 | 7063.4 |
| comparison | 0.40 | 0.30 | 6.337 | 10.550 | 3266.6 | 6865.2 |
| aggregation | 0.30 | 0.40 | 3.001 | 5.793 | 3221.8 | 6968.4 |

## Tong quan dinh luong

| Metric | Flat RAG | Graph RAG | Nhan xet |
|---|---:|---:|---|
| Avg correctness (0-1) | 0.525 | 0.575 | Graph RAG nhinh hon |
| Avg tokens/question | 3307.80 | 7009.80 | Graph RAG dung ~2.12x token |
| Avg time/question (s) | 3.897 | 7.037 | Graph RAG cham hon ~1.81x |

## Nhan xet chat luong (thu cong tu output hien tai)

### Diem manh cua Graph RAG
- Co xu huong tra loi duoc mot so cau multi-hop/comparison ma Flat RAG bo qua.
- Vi du: cau "CEO cua cong ty so huu LinkedIn la ai?" -> Graph RAG tra loi Satya Nadella, Flat RAG bao khong du thong tin.

### Diem yeu cua Graph RAG
- Ton token va thoi gian cao hon ro ret.
- O mot so cau aggregation, cau tra loi dai va co dau hieu lap luan khong chat, de phat sinh thong tin khong chinh xac.
- Vi du: cau "co bao nhieu cong ty duoc thanh lap sau 2015" co noi dung tu mau thuan trong cung mot cau tra loi.

### Diem manh cua Flat RAG
- Nhanh hon va tiet kiem token hon dang ke.
- O cac cau fact don gian (single-hop), ket qua gon va dung o muc co ban.

### Diem yeu cua Flat RAG
- De roi vao "khong du thong tin" o nhom multi-hop/comparison.
- Do sau ly giai va tong hop thap hon khi cau hoi can ket hop nhieu manh thong tin.

## Ket luan
- Accuracy: Graph RAG cao hon nhe (0.575 vs 0.525).
- Latency: Flat RAG tot hon ro ret.
- Cost: Flat RAG tot hon ro ret.
- Chon model theo muc tieu:
	- Uu tien quality: Graph RAG
	- Uu tien toc do + chi phi: Flat RAG

## De xuat buoc tiep theo
1. Bo sung truong `correctness` co cham diem thu cong (0-1) cho tung cau de co ket luan chat luong khach quan.
2. Gioi han context Graph RAG (cat bot node/relation, rerank) de giam token.
3. Tach benchmark thanh 2 che do: cost-first (Flat) va quality-first (Graph) de de chon cho tung bai toan.
