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
