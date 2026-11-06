from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("harness")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "account_balance_adapter", ROOT / "adapter.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
run_agent = module.run_agent

pytestmark = pytest.mark.skipif(
    __import__("os").getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)


def test_balance_tool_correctness() -> None:
    result = run_agent("查询用户 1001 的账户余额")
    assert "1200" in result["output"]
    assert any(
        call["name"] == "query_balance" and call["arguments"].get("user_id") == "1001"
        for call in result["tool_calls"]
    )
