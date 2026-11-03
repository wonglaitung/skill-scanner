from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_agent import HarnessAgentAdapter
from harness_tools import build_tools


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config = (options or {}).get("config", {}) or {}
    adapter = HarnessAgentAdapter(
        skill_path=Path(
            config.get("skillPath", "skills/account-balance-query/SKILL.md")
        ),
        model=config.get("model", os.getenv("SKILL_MODEL", "qwen3")),
        api_base=config.get(
            "apiBaseUrl",
            os.getenv("SKILL_API_BASE", "http://localhost:8086/v1"),
        ),
        tools=build_tools(config.get("toolSet", "default")),
        max_iterations=int(config.get("maxSteps", 10)),
        api_key=config.get("apiKey", os.getenv("SKILL_API_KEY", "local-placeholder")),
    )
    result = asyncio.run(adapter.invoke(prompt))
    return {
        "output": result.output,
        "metadata": {
            **result.metadata,
            "tool_calls": [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "result": call.result,
                    "error": call.error,
                }
                for call in result.tool_calls
            ],
        },
    }
