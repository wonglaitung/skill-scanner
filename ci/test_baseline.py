from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("baseline", ROOT / "scripts" / "baseline.py")
baseline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(baseline)


def test_summarize_values() -> None:
    result = baseline.summarize_values([1.0, 0.5, 1.0])
    assert result["mean"] == 0.8333
    assert result["min"] == 0.5
    assert result["max"] == 1.0
    assert result["n"] == 3


def test_find_flaky() -> None:
    runs = [
        {"cases": {"a": {"passed": True}, "b": {"passed": True}}},
        {"cases": {"a": {"passed": False, "reason": "boom"}, "b": {"passed": True}}},
        {"cases": {"a": {"passed": True}, "b": {"passed": True}}},
    ]
    flaky = baseline.find_flaky(runs)
    assert len(flaky) == 1
    assert flaky[0]["case"] == "a"
    assert flaky[0]["passed"] == 2
    assert flaky[0]["failed"] == 1
    assert flaky[0]["reasons"] == ["boom"]
