import json
import requests
import os

import re
from typing import Optional


# Config
BASE_URL = os.getenv(
    "GEN_COMMENTARY_URL",
    "http://localhost:8000/v1/chat/completions"
)
MODEL = os.getenv(
    "GEN_COMMENTARY_MODEL",
    "qwen3-30b-a3b-thinking-fp8"
)


system_prompt = """
You are a chess commentator. 
Given the current board position in a string representation, provide a very short comment of the game. 
Provide your response in exactly one sentence in the shortest possible way. 
Please provide your answer between <answer> and </answer> tags.
"""


def extract_last_answer_after_think(text: str) -> Optional[str]:
    """
    Returns the last substring between <answer> and </answer> that occurs
    AFTER the final </think> tag. If not found (or no </think>), returns None.
    Tag matching is case-insensitive and spans newlines.
    """
    # Find the end position of the last </think>
    last_think_end = -1
    for m in re.finditer(r"</think\s*>", text, flags=re.IGNORECASE):
        last_think_end = m.end()
    if last_think_end == -1:
        return None  # no </think> present

    # Find all <answer>...</answer> AFTER that position
    pattern = re.compile(r"<answer\s*>(.*?)</answer\s*>", re.IGNORECASE | re.DOTALL)
    matches = list(pattern.finditer(text, pos=last_think_end))
    if not matches:
        return None

    return matches[-1].group(1).strip()


def chat(board_content: str, **kwargs):
    """
    Generate commentary for a given board state.

    Args:
        board_content: A string describing the board (e.g., FEN or ASCII).
        **kwargs: Optional overrides for generation parameters:
            - max_tokens (int)
            - temperature (float)
            - top_p (float)

    Returns:
        A one-sentence commentary string.
    """
    messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": board_content},
    ]
    payload = {
        "model": MODEL,
        "messages": messages,
        # add any OpenAI-style params you want:
        "max_tokens": kwargs.get("max_tokens", 512),
        "temperature": kwargs.get("temperature", 0.2),
        "top_p": kwargs.get("top_p", 1.0),
        # "stream": True,  # uncomment if your server supports SSE streaming
    }
    r = requests.post(
        BASE_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    # Most OpenAI-compatible servers return the text here:
    generated_text = data["choices"][0]["message"]["content"]
    final_text = extract_last_answer_after_think(generated_text)
    if final_text is None:
        return "No comment."
    else:
        return final_text
