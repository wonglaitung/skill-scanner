from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("deepeval")
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.models import LocalModel
from deepeval.test_case import LLMTestCase

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("expense-policy-qa_adapter", ROOT / "adapter.py")
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


def test_relevancy() -> None:
    case = '出差住宿标准是多少？'
    result = run_prompt(case)
    assert_test(
        LLMTestCase(input=case, actual_output=result["output"]),
        [AnswerRelevancyMetric(threshold=0.6, model=JUDGE)],
    )
