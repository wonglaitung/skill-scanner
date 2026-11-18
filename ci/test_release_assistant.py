from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from release_assistant import decide_failures, detect_template_warnings, write_summary  # noqa: E402


def test_release_assistant_init(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: demo\n"
        "license: internal\n"
        "allowed-tools: []\n"
        "metadata:\n"
        "  owner: demo\n"
        "  risk-level: S2\n"
        "  version: 0.1.0\n"
        "---\n\n# Demo\n",
        encoding="utf-8",
    )
    targets = tmp_path / "targets"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/release_assistant.py",
            "init",
            "--source",
            str(source),
            "--name",
            "demo-skill",
            "--owner",
            "demo",
            "--targets",
            str(targets),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "SKILL_IN_DOCKER": "1",
            "SKILL_API_KEY": "fake-secret-value",
        },
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (targets / "demo-skill" / "manifest.yaml").exists()
    assert "[1/2] 初始化目标包结构 | 开始" in proc.stdout
    assert "[2/2] 生成完整性锁 | OK" in proc.stdout
    assert "输入 | cwd=" in proc.stdout
    assert "SKILL_API_KEY=<set>" in proc.stdout
    assert "fake-secret-value" not in proc.stdout


def test_decide_failures_covers_every_round_and_l3() -> None:
    result = {
        "steps": {
            "preflight": 0,
            "manual_check": [0, 2, 0],
            "baseline_collect": 0,
            "gate": 0,
        },
        "l3_enabled": False,
    }
    assert decide_failures(result) == ["manual_check round 2"]

    result["l3_enabled"] = True
    result["steps"]["l3"] = 1
    assert decide_failures(result) == ["manual_check round 2", "l3"]


def test_decide_failures_ignores_unexecuted_steps() -> None:
    result = {"steps": {"preflight": 1}, "l3_enabled": True}
    assert decide_failures(result) == ["preflight"]


def test_write_summary_links_real_reports_and_failures(tmp_path: Path) -> None:
    result = {
        "skill": "demo-skill",
        "targets": "targets",
        "timestamp": "2026-11-17-000000",
        "steps": {"preflight": 0, "manual_check": [0, 1], "gate": 0},
        "l3_enabled": False,
        "logs": [
            {
                "step": "前置校验 preflight",
                "path": "reports/logs/preflight.log",
                "exit": 0,
            }
        ],
        "warnings": ["Promptfoo 用例仍是模板占位，需替换为业务用例"],
        "rounds": [
            {
                "index": 1,
                "status": 0,
                "report": str(tmp_path / "round-1" / "report.md"),
                "metrics": {"metrics": {"promptfoo": {"pass_rate": 1.0, "total": 2}}},
            },
            {
                "index": 2,
                "status": 1,
                "report": str(tmp_path / "round-2" / "report.md"),
                "metrics": {
                    "metrics": {
                        "promptfoo": {
                            "pass_rate": 0.5,
                            "total": 2,
                            "findings": [{"input": "q", "reason": "bad output"}],
                        }
                    }
                },
            },
        ],
    }
    write_summary(tmp_path, result)

    data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert data["decision"] == "FAIL"
    assert "manual_check round 2" in data["failures"]

    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Decision: FAIL" in text
    assert "round-2/report.md" in text
    assert "bad output" in text
    assert "模板占位" in text
    assert "reports/logs/preflight.log" in text


def test_detect_template_warnings(tmp_path: Path) -> None:
    target = tmp_path / "targets" / "demo-skill"
    (target / "evals").mkdir(parents=True)
    (target / "evals" / "promptfoo.yaml").write_text(
        "tests:\n  - vars:\n      user_input: 请替换为真实测试输入\n",
        encoding="utf-8",
    )
    (target / "adapter.py").write_text(
        "def run(user_input):\n    # TODO: implement tool execution\n",
        encoding="utf-8",
    )
    warnings = detect_template_warnings(tmp_path / "targets", "demo-skill")
    assert len(warnings) == 2
