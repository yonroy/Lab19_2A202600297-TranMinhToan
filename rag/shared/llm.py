import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

LLM_MODEL = "gpt-4o-mini"


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
    """Gọi LLM, trả về nội dung text."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
