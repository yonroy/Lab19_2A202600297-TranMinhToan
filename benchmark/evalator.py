import json
import re
import time
import traceback
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAG_ROOT = PROJECT_ROOT / "rag"
if str(RAG_ROOT) not in sys.path:
	sys.path.insert(0, str(RAG_ROOT))

from flat_rag.rag import answer as flat_rag_answer
from graph_rag.rag import answer as graph_rag_answer
from shared.llm import call_llm, call_llm_judge


Question = dict[str, Any]
ModelResult = dict[str, Any]
BenchmarkResult = dict[str, Any]

JUDGE_SYSTEM_PROMPT = """You are a strict evaluator for question answering.
Score the candidate answer against the reference answer on a 0-1 scale:
- 1.0: fully correct and complete
- 0.5: partially correct
- 0.0: incorrect, missing, or contradictory
Return only one number between 0 and 1 (e.g., 0, 0.5, 1)."""


def load_questions(question_file: str | Path) -> list[Question]:
	question_path = Path(question_file)
	with question_path.open("r", encoding="utf-8") as f:
		questions = json.load(f)
	return questions


def create_result_template(question: str) -> BenchmarkResult:
	# Keep schema aligned with the requested benchmark output format.
	return {
		"question": question,
		"flat_rag": {
			"answer": "",
			"tokens_used": 0,
			"time_seconds": 0.0,
			"correctness": 0.0,
		},
		"graph_rag": {
			"answer": "",
			"tokens_used": 0,
			"time_seconds": 0.0,
			"correctness": 0.0,
		},
	}


def _call_system(rag_fn: Callable[[str], Any], question: str) -> ModelResult:
	started = time.perf_counter()
	try:
		raw_output = rag_fn(question)
		elapsed = round(time.perf_counter() - started, 4)
	except Exception as exc:
		elapsed = round(time.perf_counter() - started, 4)
		return {
			"answer": f"ERROR: {exc}",
			"tokens_used": 0,
			"time_seconds": elapsed,
			"correctness": 0.0,
		}

	if isinstance(raw_output, dict):
		answer = str(raw_output.get("answer", ""))
		tokens_used = int(raw_output.get("tokens_used", 0) or 0)
	else:
		answer = str(raw_output)
		tokens_used = 0

	return {
		"answer": answer,
		"tokens_used": tokens_used,
		"time_seconds": elapsed,
		"correctness": 0.0,
	}


def _extract_score(text: str) -> float:
	match = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", text.strip())
	if not match:
		return 0.0
	value = float(match.group(1))
	return max(0.0, min(1.0, value))


def judge_correctness(question: str, reference_answer: str, candidate_answer: str) -> float:
	if not candidate_answer or candidate_answer.startswith("ERROR:"):
		return 0.0

	judge_prompt = (
		f"Question: {question}\n"
		f"Reference answer: {reference_answer}\n"
		f"Candidate answer: {candidate_answer}\n\n"
		"Return only the numeric score in [0,1]."
	)

	try:
		judge_output = call_llm_judge(JUDGE_SYSTEM_PROMPT, judge_prompt, max_tokens=16)
		return _extract_score(judge_output)
	except Exception:
		return 0.0


def run_benchmark(
	questions: list[Question],
	flat_rag_fn: Callable[[str], Any],
	graph_rag_fn: Callable[[str], Any],
) -> list[BenchmarkResult]:
	results: list[BenchmarkResult] = []

	for item in questions:
		question_text = item["question"]
		reference_answer = str(item.get("reference_answer", ""))
		result = create_result_template(question_text)
		flat_result = _call_system(flat_rag_fn, question_text)
		graph_result = _call_system(graph_rag_fn, question_text)

		flat_result["correctness"] = judge_correctness(
			question_text,
			reference_answer,
			flat_result["answer"],
		)
		graph_result["correctness"] = judge_correctness(
			question_text,
			reference_answer,
			graph_result["answer"],
		)

		result["flat_rag"] = flat_result
		result["graph_rag"] = graph_result
		results.append(result)

	return results


def save_results(results: list[BenchmarkResult], output_file: str | Path) -> None:
	output_path = Path(output_file)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent=2)


# gpt-4o-mini pricing (USD per token)
_PRICE_INPUT_PER_TOKEN  = 0.15 / 1_000_000   # $0.15 / 1M input tokens
_PRICE_OUTPUT_PER_TOKEN = 0.60 / 1_000_000   # $0.60 / 1M output tokens
_INPUT_RATIO  = 0.85   # assumed fraction of total tokens that are input
_OUTPUT_RATIO = 0.15


def _estimate_cost(total_tokens: float) -> float:
	"""Estimate USD cost from total token count using gpt-4o-mini pricing."""
	return (
		total_tokens * _INPUT_RATIO  * _PRICE_INPUT_PER_TOKEN
		+ total_tokens * _OUTPUT_RATIO * _PRICE_OUTPUT_PER_TOKEN
	)


def compute_summary(
	results: list[BenchmarkResult],
	questions: list[Question],
) -> dict:
	"""
	Compute per-type and overall statistics:
	  accuracy, avg latency (s), avg tokens, estimated USD cost.
	"""
	# Build question-type lookup by question text
	type_by_question: dict[str, str] = {q["question"]: q.get("type", "unknown") for q in questions}

	# Accumulate per-type buckets
	buckets: dict[str, dict] = {}

	for r in results:
		q_type = type_by_question.get(r["question"], "unknown")
		if q_type not in buckets:
			buckets[q_type] = {
				"flat_correctness": [],
				"graph_correctness": [],
				"flat_time": [],
				"graph_time": [],
				"flat_tokens": [],
				"graph_tokens": [],
			}
		b = buckets[q_type]
		b["flat_correctness"].append(r["flat_rag"]["correctness"])
		b["graph_correctness"].append(r["graph_rag"]["correctness"])
		b["flat_time"].append(r["flat_rag"]["time_seconds"])
		b["graph_time"].append(r["graph_rag"]["time_seconds"])
		b["flat_tokens"].append(r["flat_rag"]["tokens_used"])
		b["graph_tokens"].append(r["graph_rag"]["tokens_used"])

	def _avg(lst: list) -> float:
		return round(sum(lst) / len(lst), 4) if lst else 0.0

	def _total(lst: list) -> float:
		return round(sum(lst), 4)

	per_type = {}
	all_flat_correct, all_graph_correct = [], []
	all_flat_time,    all_graph_time    = [], []
	all_flat_tokens,  all_graph_tokens  = [], []

	for q_type, b in sorted(buckets.items()):
		per_type[q_type] = {
			"count": len(b["flat_correctness"]),
			"flat_accuracy":    _avg(b["flat_correctness"]),
			"graph_accuracy":   _avg(b["graph_correctness"]),
			"flat_avg_time_s":  _avg(b["flat_time"]),
			"graph_avg_time_s": _avg(b["graph_time"]),
			"flat_avg_tokens":  _avg(b["flat_tokens"]),
			"graph_avg_tokens": _avg(b["graph_tokens"]),
			"flat_cost_usd":    round(_estimate_cost(_total(b["flat_tokens"])), 6),
			"graph_cost_usd":   round(_estimate_cost(_total(b["graph_tokens"])), 6),
		}
		all_flat_correct  += b["flat_correctness"]
		all_graph_correct += b["graph_correctness"]
		all_flat_time     += b["flat_time"]
		all_graph_time    += b["graph_time"]
		all_flat_tokens   += b["flat_tokens"]
		all_graph_tokens  += b["graph_tokens"]

	overall = {
		"count": len(results),
		"flat_accuracy":     _avg(all_flat_correct),
		"graph_accuracy":    _avg(all_graph_correct),
		"flat_avg_time_s":   _avg(all_flat_time),
		"graph_avg_time_s":  _avg(all_graph_time),
		"flat_total_time_s": _total(all_flat_time),
		"graph_total_time_s": _total(all_graph_time),
		"flat_avg_tokens":   _avg(all_flat_tokens),
		"graph_avg_tokens":  _avg(all_graph_tokens),
		"flat_total_tokens": int(_total(all_flat_tokens)),
		"graph_total_tokens": int(_total(all_graph_tokens)),
		"flat_total_cost_usd":  round(_estimate_cost(_total(all_flat_tokens)), 6),
		"graph_total_cost_usd": round(_estimate_cost(_total(all_graph_tokens)), 6),
	}

	return {"overall": overall, "per_type": per_type}


def print_summary(summary: dict) -> None:
	"""Print a human-readable summary table to stdout."""
	ov = summary["overall"]
	print("\n" + "=" * 70)
	print("BENCHMARK SUMMARY")
	print("=" * 70)
	print(f"{'Metric':<35} {'Flat RAG':>14} {'Graph RAG':>14}")
	print("-" * 70)
	print(f"{'Accuracy (avg correctness)':<35} {ov['flat_accuracy']:>14.4f} {ov['graph_accuracy']:>14.4f}")
	print(f"{'Avg latency / question (s)':<35} {ov['flat_avg_time_s']:>14.3f} {ov['graph_avg_time_s']:>14.3f}")
	print(f"{'Total time (s)':<35} {ov['flat_total_time_s']:>14.2f} {ov['graph_total_time_s']:>14.2f}")
	print(f"{'Avg tokens / question':<35} {ov['flat_avg_tokens']:>14.1f} {ov['graph_avg_tokens']:>14.1f}")
	print(f"{'Total tokens':<35} {ov['flat_total_tokens']:>14,} {ov['graph_total_tokens']:>14,}")
	print(f"{'Total cost (USD, estimated)':<35} ${ov['flat_total_cost_usd']:>13.6f} ${ov['graph_total_cost_usd']:>13.6f}")
	print("=" * 70)

	print(f"\n{'Type':<14} {'Flat Acc':>9} {'Graph Acc':>9} {'Flat t(s)':>10} {'Graph t(s)':>10} {'Flat $':>10} {'Graph $':>10}")
	print("-" * 75)
	for q_type, s in summary["per_type"].items():
		print(
			f"{q_type:<14} {s['flat_accuracy']:>9.2f} {s['graph_accuracy']:>9.2f}"
			f" {s['flat_avg_time_s']:>10.3f} {s['graph_avg_time_s']:>10.3f}"
			f" {s['flat_cost_usd']:>10.6f} {s['graph_cost_usd']:>10.6f}"
		)
	print("=" * 75)


if __name__ == "__main__":
	question_file = PROJECT_ROOT / "benchmark" / "question.json"
	output_file   = PROJECT_ROOT / "benchmark" / "result.json"
	summary_file  = PROJECT_ROOT / "benchmark" / "summary.json"

	try:
		questions = load_questions(question_file)
		results = run_benchmark(
			questions=questions,
			flat_rag_fn=lambda q: flat_rag_answer(q, top_k=5),
			graph_rag_fn=lambda q: graph_rag_answer(q, top_k=5, hop=2),
		)
		save_results(results, output_file)
		print(f"Benchmark done. Saved {len(results)} results to: {output_file}")

		summary = compute_summary(results, questions)
		print_summary(summary)

		summary_file.parent.mkdir(parents=True, exist_ok=True)
		with summary_file.open("w", encoding="utf-8") as f:
			json.dump(summary, f, ensure_ascii=False, indent=2)
		print(f"\nSummary saved to: {summary_file}")

	except Exception:
		print("Benchmark failed with unexpected error:")
		print(traceback.format_exc())
