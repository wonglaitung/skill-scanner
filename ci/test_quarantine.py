from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quarantine  # noqa: E402

spec = importlib.util.spec_from_file_location("baseline", ROOT / "scripts" / "baseline.py")
baseline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(baseline)


def test_active_entries_filters_expired(tmp_path: Path) -> None:
    config = tmp_path / "quarantine.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "demo": [
                        {"case": "a", "owner": "o", "expires": "2099-01-01"},
                        {"case": "b", "owner": "o", "expires": "2000-01-01"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    entries = quarantine.active_entries("demo", config, today=date(2026, 1, 1))
    assert [entry["case"] for entry in entries] == ["a"]
    assert quarantine.match(entries, "a")["owner"] == "o"
    assert quarantine.match(entries, "b") is None


def test_find_flaky_skips_quarantined() -> None:
    runs = [
        {"cases": {"a": {"passed": True}, "b": {"passed": True, "quarantined": True}}},
        {"cases": {"a": {"passed": False}, "b": {"passed": False, "quarantined": True}}},
    ]
    flaky = baseline.find_flaky(runs)
    assert [item["case"] for item in flaky] == ["a"]


def test_parse_promptfoo_excludes_quarantined(tmp_path: Path) -> None:
    import manual_check

    data = {
        "results": {
            "results": [
                {"vars": {"user_input": "ok"}, "success": True},
                {
                    "vars": {"user_input": "bad"},
                    "success": False,
                    "error": "boom",
                },
            ]
        }
    }
    path = tmp_path / "promptfoo.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    metrics = manual_check.parse_promptfoo(
        path, [{"case": "bad", "owner": "o", "expires": "2099-01-01", "reason": "known"}]
    )
    assert metrics["passed"] == 1
    assert metrics["failed"] == 0
    assert metrics["errors"] == 0
    assert metrics["quarantined"] == 1
    assert metrics["pass_rate"] == 1.0
