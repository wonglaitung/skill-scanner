from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "manual_check", ROOT / "scripts" / "manual_check.py"
)
manual_check = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(manual_check)


def test_required_skipped_counts_as_failure() -> None:
    steps = [
        {
            "name": "promptfoo",
            "status": "skipped",
            "required": True,
            "reason": "no config",
        },
        {"name": "semgrep", "status": "skipped", "required": False},
        {"name": "validate", "status": "passed"},
        {"name": "deepeval", "status": "failed", "required": True},
    ]
    assert [item["name"] for item in manual_check.hard_failures(steps)] == [
        "promptfoo",
        "deepeval",
    ]


def test_optional_skipped_is_not_a_failure() -> None:
    steps = [
        {"name": "security", "status": "skipped", "required": False},
        {"name": "garak", "status": "passed"},
    ]
    assert manual_check.hard_failures(steps) == []


def test_build_finding_prefers_readable_reason_and_adds_excerpt() -> None:
    item = {
        "failureReason": 1,
        "error": 'Expected output to not contain "张三"',
        "response": {"output": "我不能点名，但张三的失误是..."},
    }
    finding = manual_check._build_finding(item, "点名张三", None)
    assert finding["reason"] == 'Expected output to not contain "张三"'
    assert "张三" in finding["output_excerpt"]
    assert finding["source"] == "promptfoo"


def test_parse_deepeval_extracts_failed_case_names() -> None:
    text = "FAILED x/test_target.py::test_pii\nFAILED x/test_target.py::test_leak\n1 passed, 2 failed"
    result = manual_check.parse_deepeval(text, 1)
    assert result["failed_cases"] == ["test_pii", "test_leak"]
    assert result["failed"] == 2


def test_parse_deepeval_extracts_failure_details() -> None:
    text = (
        "======== FAILURES ========\n"
        "_______ test_pii _______\n"
        "    assert 'x' not in out\n"
        "E   AssertionError: assert 'x' not in 'x shown'\n"
        "_______ test_leak _______\n"
        "E   assert 0.07 >= 0.7\n"
        "[deepeval] FaithfulnessMetric: score=0.073 reason=fabricated details\n"
        "======== short test summary ========\n"
        "FAILED x/test_target.py::test_pii\n"
        "FAILED x/test_target.py::test_leak\n"
        "1 passed, 2 failed"
    )
    result = manual_check.parse_deepeval(text, 1)
    details = {d["case"]: d["reason"] for d in result["failed_details"]}
    assert "AssertionError" in details["test_pii"]
    assert "0.073" in details["test_leak"]
    assert "fabricated" in details["test_leak"]
