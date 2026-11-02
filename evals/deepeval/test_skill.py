from __future__ import annotations

import os

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.models import LocalModel
from deepeval.test_case import LLMTestCase

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

CONTEXT = [
    "员工出差住宿标准：一线城市每晚不超过 600 元，二线城市不超过 400 元，报销时需提供发票。"
]


def test_skill_output_quality() -> None:
    test_case = LLMTestCase(
        input="出差住宿标准是多少？",
        actual_output="一线城市每晚不超过 600 元，二线城市不超过 400 元，报销时需提供发票。",
        context=CONTEXT,
        retrieval_context=CONTEXT,
    )
    assert_test(
        test_case,
        [
            AnswerRelevancyMetric(threshold=0.7, model=JUDGE),
            FaithfulnessMetric(threshold=0.7, model=JUDGE),
            HallucinationMetric(threshold=0.5, model=JUDGE),
        ],
    )
