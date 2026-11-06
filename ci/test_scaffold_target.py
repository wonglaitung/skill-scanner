from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_prompt_target(tmp_path: Path) -> None:
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
            "scripts/scaffold_target.py",
            "--source",
            str(source),
            "--name",
            "demo-skill",
            "--owner",
            "demo",
            "--risk",
            "S2",
            "--type",
            "prompt",
            "--level",
            "L2",
            "--targets",
            str(targets),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    target = targets / "demo-skill"
    assert (target / "SKILL.md").exists()
    assert (target / "manifest.yaml").exists()
    assert (target / "adapter.py").exists()
    assert (target / "evals" / "promptfoo.yaml").exists()
