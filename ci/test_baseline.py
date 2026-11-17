from __future__ import annotations

import importlib.util
import json
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


def test_gate_detects_regression(tmp_path, monkeypatch) -> None:
    reports = tmp_path / "reports"
    baselines = tmp_path / "baselines"
    monkeypatch.setattr(baseline, "REPORTS_DIR", reports)
    monkeypatch.setattr(baseline, "BASELINES_DIR", baselines)

    report_dir = reports / "demo" / "2026-01-01-000000"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.json").write_text(
        '{"skill":"demo","timestamp":"2026-01-01-000000",'
        '"metrics":{"promptfoo":{"pass_rate":0.9},"deepeval":{"pass_rate":1.0}}}',
        encoding="utf-8",
    )

    baselines.mkdir()
    (baselines / "demo.json").write_text(
        '{"schema_version":2,"skill":"demo","aggregate":{"run_count":3,'
        '"promptfoo":{"pass_rate":{"mean":1.0,"std":0.0}},'
        '"deepeval":{"pass_rate":{"mean":1.0,"std":0.0}}},"flaky":[]}',
        encoding="utf-8",
    )
    assert baseline.gate("demo", None, 0.05, 3, False) == 1
    assert baseline.gate("demo", None, 0.2, 3, False) == 0


def test_collect_from_release_report_dir(tmp_path, monkeypatch) -> None:
    targets = tmp_path / "targets"
    (targets / "demo" / "evals").mkdir(parents=True)
    report_dir = tmp_path / "release-1"
    monkeypatch.setattr(baseline, "REPORTS_DIR", tmp_path / "reports")

    for index, rate in enumerate((1.0, 0.9, 0.8), start=1):
        round_dir = report_dir / f"round-{index}"
        round_dir.mkdir(parents=True)
        summary = {
            "skill": "demo",
            "level": "L2",
            "agent": False,
            "timestamp": f"2026-11-1{index}-000000",
            "model": "qwen3",
            "api_base": "http://localhost:8086/v1",
            "metrics": {
                "promptfoo": {
                    "pass_rate": rate,
                    "total": 2,
                    "passed": 2,
                    "failed": 0,
                    "errors": 0,
                    "findings": [],
                },
                "deepeval": {"pass_rate": 1.0},
            },
        }
        (round_dir / "summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        (round_dir / "promptfoo.json").write_text(
            '{"results":{"results":[]}}', encoding="utf-8"
        )

    code = baseline.collect("demo", 3, None, None, None, targets, report_dir)
    assert code == 0
    data = json.loads(
        (targets / "demo" / "evals" / "baseline.json").read_text(encoding="utf-8")
    )
    assert data["aggregate"]["run_count"] == 3
    assert data["aggregate"]["promptfoo"]["pass_rate"]["mean"] == 0.9
