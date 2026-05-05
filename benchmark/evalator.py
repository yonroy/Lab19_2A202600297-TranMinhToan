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
from shared.llm import call_llm


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
		judge_output = call_llm(JUDGE_SYSTEM_PROMPT, judge_prompt, max_tokens=16)
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


if __name__ == "__main__":
	question_file = PROJECT_ROOT / "benchmark" / "question.json"
	output_file = PROJECT_ROOT / "benchmark" / "result.json"

	try:
		questions = load_questions(question_file)
		results = run_benchmark(
			questions=questions,
			flat_rag_fn=lambda q: flat_rag_answer(q, top_k=5),
			graph_rag_fn=lambda q: graph_rag_answer(q, top_k=5),
		)
		save_results(results, output_file)
		print(f"Benchmark done. Saved {len(results)} results to: {output_file}")
	except Exception:
		print("Benchmark failed with unexpected error:")
		print(traceback.format_exc())
