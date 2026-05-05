import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

LLM_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o"


def call_llm_with_usage(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> dict:
    """Call LLM and return text + token usage for benchmarking."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    usage = response.usage
    answer = response.choices[0].message.content.strip()
    return {
        "answer": answer,
        "tokens_used": int(getattr(usage, "total_tokens", 0) or 0),
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "model": LLM_MODEL,
    }


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
    """Gọi LLM, trả về nội dung text."""
    return call_llm_with_usage(system_prompt, user_prompt, max_tokens=max_tokens)["answer"]


def call_llm_judge(system_prompt: str, user_prompt: str, max_tokens: int = 16) -> str:
    """Gọi judge model (gpt-4o) — chính xác hơn cho LLM-as-judge scoring."""
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
