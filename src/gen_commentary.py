import json
import requests
    

BASE_URL = "http://20.66.111.167:31022/v1/chat/completions"
MODEL = "qwen3-30b-a3b-thinking-fp8"  # use the exact id your server exposes

import re
from typing import Optional

def extract_answer(text: str) -> Optional[str]:
    """
    Returns the substring between <answer> and </answer>.
    If no such tagged section exists, returns None.
    Matches across newlines and is case-insensitive for the tags.
    """
    m = re.search(r"<answer>(.*?)</answer>", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else None


system_prompt = """
You are Magnus Carlsen. 
Given the current board position in a string representation, provide a very short comment of the game. 
Provide your response in exactly one sentence in the shortest possible way. 
Please provide your answer between <answer> and </answer> tags.
"""


def chat(board_content: str, **kwargs):
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
    final_text = extract_answer(generated_text)
    if final_text is None:
        return "No comment."
    else:
        return final_text
