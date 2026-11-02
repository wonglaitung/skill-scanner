from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_adapter import LocalGatewayAdapter


def call_api(prompt: str, options: dict, context: dict) -> dict:
    adapter = LocalGatewayAdapter.from_env()
    result = adapter.invoke(prompt)
    return {
        "output": result.output,
        "metadata": {
            **result.metadata,
            "trace_id": result.trace_id,
        },
    }
