from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    "---\n"
    "name: demo-skill\n"
    "description: demo\n"
    "license: internal\n"
    "allowed-tools: []\n"
    "metadata:\n"
    "  owner: demo\n"
    "  risk-level: S2\n"
    "  version: 0.1.0\n"
    "---\n\n# Demo\n"
)


def run_lock(targets: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/skill_lock.py", "--targets", str(targets), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )


def test_external_targets_generate_and_verify(tmp_path: Path) -> None:
    targets = tmp_path / "targets"
    skill = targets / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(SOURCE, encoding="utf-8")

    generated = run_lock(targets, "generate")
    assert generated.returncode == 0, generated.stdout + generated.stderr
    assert (targets / "skills.lock.json").exists()

    verified = run_lock(targets, "verify", "--skill", "demo-skill")
    assert verified.returncode == 0, verified.stdout + verified.stderr

    (skill / "SKILL.md").write_text(SOURCE + "\ntampered\n", encoding="utf-8")
    tampered = run_lock(targets, "verify", "--skill", "demo-skill")
    assert tampered.returncode == 1
    assert "hash mismatch" in tampered.stdout


def test_generate_preserves_other_lock_entries(tmp_path: Path) -> None:
    targets = tmp_path / "targets"
    first = targets / "first-skill"
    second = targets / "second-skill"
    for path, name in ((first, "first-skill"), (second, "second-skill")):
        path.mkdir(parents=True)
        text = SOURCE.replace("demo-skill", name)
        (path / "SKILL.md").write_text(text, encoding="utf-8")

    assert run_lock(targets, "generate").returncode == 0
    (second / "SKILL.md").unlink()
    shutil.rmtree(second)
    assert run_lock(targets, "generate").returncode == 0

    data = json.loads((targets / "skills.lock.json").read_text(encoding="utf-8"))
    assert "first-skill" in data["skills"]
