from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scan_all_preflight() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/scan_all.py",
            "--targets",
            "targets",
            "--only",
            "write-report",
            "--out",
            "/tmp/opencode/scan_all_test",
            "--skip-network",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "write-report" in proc.stdout
