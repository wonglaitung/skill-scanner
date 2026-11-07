from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_target_preflight_prompt() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/preflight.py",
            "--targets",
            "targets",
            "--skill",
            "write-report",
            "--risk",
            "S2",
            "--level",
            "L2",
            "--skip-network",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_target_preflight_tool() -> None:
    if not (ROOT / ".venv-harness" / "bin" / "python").exists():
        pytest.skip("harness venv not installed in this environment")
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/preflight.py",
            "--targets",
            "targets",
            "--skill",
            "account-balance-query",
            "--risk",
            "S2",
            "--level",
            "L2",
            "--agent",
            "--skip-network",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
