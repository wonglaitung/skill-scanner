from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.models import LocalModel
from deepeval.test_case import LLMTestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "adapters"))

from skill_adapter import LocalGatewayAdapter  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)

JUDGE = LocalModel(
    model=os.getenv("JUDGE_MODEL", "local-judge"),
    base_url=os.getenv(
        "JUDGE_API_BASE", os.getenv("SKILL_API_BASE", "http://localhost:8086/v1")
    ),
    api_key=os.getenv(
        "JUDGE_API_KEY", os.getenv("SKILL_API_KEY", "local-placeholder")
    ),
    temperature=0,
)

CASES = [
    ("write-report", "请写一份算力资源申请的汇报开头"),
    ("system-specification", "解释 OMS 并说明业务含义"),
    ("manager-report", "写一份算力申请汇报"),
]


@pytest.mark.parametrize("skill,input_text", CASES)
def test_s2_skill_relevancy(skill: str, input_text: str) -> None:
    adapter = LocalGatewayAdapter.from_env(
        skill_path=f"skills/{skill}/SKILL.md",
    )
    result = adapter.invoke(input_text)
    test_case = LLMTestCase(input=input_text, actual_output=result.output)
    assert_test(
        test_case,
        [AnswerRelevancyMetric(threshold=0.7, model=JUDGE)],
    )
