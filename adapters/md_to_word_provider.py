from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from md_to_word_adapter import MdToWordAdapter


def call_api(prompt: str, options: dict, context: dict) -> dict:
    adapter = MdToWordAdapter.from_env()
    result = adapter.convert(prompt)
    if result.metadata.get("error"):
        return {
            "output": "",
            "metadata": result.metadata,
            "error": result.metadata["error"],
        }
    return {
        "output": result.output,
        "metadata": result.metadata,
    }
