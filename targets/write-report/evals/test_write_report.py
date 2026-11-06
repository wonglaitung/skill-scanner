from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.models import LocalModel
from deepeval.test_case import LLMTestCase

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "write_report_adapter", ROOT / "adapter.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
run_prompt = module.run_prompt

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)

JUDGE = LocalModel(
    model=os.getenv("JUDGE_MODEL", "qwen3"),
    base_url=os.getenv("JUDGE_API_BASE", "http://localhost:8086/v1"),
    api_key=os.getenv("JUDGE_API_KEY", "local-placeholder"),
    temperature=0,
)


def test_write_report_relevancy() -> None:
    case = "请写一份算力资源申请的汇报开头"
    result = run_prompt(case)
    test_case = LLMTestCase(input=case, actual_output=result["output"])
    assert_test(test_case, [AnswerRelevancyMetric(threshold=0.6, model=JUDGE)])
