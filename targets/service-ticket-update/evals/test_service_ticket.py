from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("harness")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("service-ticket-update_adapter", ROOT / "adapter.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
run_agent = module.run_agent

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)


def test_tool_call() -> None:
    result = run_agent('把工单 T-2001 标记为已解决，备注：已联系客户')
    assert any(
        call["name"] == "update_ticket"
        and call["arguments"].get("ticket_id") == "T-2001"
        for call in result["tool_calls"]
    )
