from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def run_prompt(user_input: str) -> dict:
    api_base = os.getenv("SKILL_API_BASE", "http://localhost:8086/v1").rstrip("/")
    response = httpx.post(
        f"{api_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('SKILL_API_KEY', 'local-placeholder')}"
        },
        json={
            "model": os.getenv("SKILL_MODEL", "qwen3"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0,
            "max_tokens": int(os.getenv("SKILL_MAX_TOKENS", "2048")),
        },
        timeout=float(os.getenv("SKILL_TIMEOUT", "180")),
    )
    response.raise_for_status()
    return {
        "output": response.json()["choices"][0]["message"]["content"],
        "metadata": {"trace_id": response.json().get("id")},
    }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del options, context
    return run_prompt(prompt)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: adapter.py run --input <text>", file=sys.stderr)
        return 2
    if sys.argv[1] == "run":
        prompt = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(run_prompt(prompt), ensure_ascii=False))
        return 0
    print(f"unknown command: {sys.argv[1]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
