from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("deepeval")
pytest.importorskip("harness")

from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, ToolCorrectnessMetric
from deepeval.models import LocalModel
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "adapters"))

from harness_agent import HarnessAgentAdapter  # noqa: E402
from harness_tools import build_tools  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)

JUDGE = LocalModel(
    model=os.getenv("JUDGE_MODEL", "local-judge"),
    base_url=os.getenv(
        "JUDGE_API_BASE", os.getenv("SKILL_API_BASE", "http://localhost:8086/v1")
    ),
    api_key=os.getenv("JUDGE_API_KEY", "local-placeholder"),
    temperature=0,
)


def test_account_balance_tool_correctness() -> None:
    adapter = HarnessAgentAdapter(
        skill_path=ROOT / "skills" / "account-balance-query" / "SKILL.md",
        model=os.getenv("SKILL_MODEL", "qwen3"),
        api_base=os.getenv("SKILL_API_BASE", "http://localhost:8086/v1"),
        tools=build_tools("query"),
        max_iterations=6,
    )
    result = asyncio.run(adapter.invoke("查询用户 1001 的账户余额"))

    test_case = LLMTestCase(
        input="查询用户 1001 的账户余额",
        actual_output=result.output,
        expected_tools=[
            ToolCall(name="query_balance", input_parameters={"user_id": "1001"})
        ],
        tools_called=[
            ToolCall(name=call.name, input_parameters=call.arguments)
            for call in result.tool_calls
        ],
    )
    assert_test(
        test_case,
        [
            AnswerRelevancyMetric(threshold=0.7, model=JUDGE),
            ToolCorrectnessMetric(
                threshold=0.8,
                model=JUDGE,
                evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            ),
        ],
    )
