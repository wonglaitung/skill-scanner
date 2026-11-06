from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("harness")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("cross-skill-router_adapter", ROOT / "adapter.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
run_agent = module.run_agent

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)


def test_tool_call() -> None:
    result = run_agent('查询我的余额，并委托 knowledge skill 做摘要')
    assert any(
        call["name"] == "delegate_to_skill"
        and call["arguments"].get("skill") == "knowledge"
        for call in result["tool_calls"]
    )
