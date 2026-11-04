from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prompt_audit", ROOT / "scripts" / "prompt_audit.py")
prompt_audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(prompt_audit)

CASES = ROOT / "evals" / "prompt_quality" / "cases"


def _audit(name: str):
    frontmatter, body = prompt_audit.parse_skill(CASES / name / "SKILL.md")
    return prompt_audit.audit_text(name, frontmatter, body)


def test_clean_seed_passes() -> None:
    result = _audit("clean")
    assert result["status"] == "passed"
    assert result["errors"] == 0
    assert result["warnings"] == 0


def test_detects_pii_phone() -> None:
    result = _audit("pii_phone")
    assert result["status"] == "failed"
    assert any(item["rule"] == "pii.phone" for item in result["findings"])


def test_detects_private_key() -> None:
    result = _audit("private_key")
    assert any(item["rule"] == "secret.private_key" for item in result["findings"])


def test_detects_prompt_leak_phrase() -> None:
    result = _audit("prompt_leak")
    assert any(item["rule"] == "prompt.leak_phrase" for item in result["findings"])


def test_detects_permission_contradiction() -> None:
    result = _audit("permission_conflict")
    assert any(item["rule"] == "permission.contradiction" for item in result["findings"])


def test_internal_path_is_warning() -> None:
    result = _audit("internal_path")
    assert result["status"] == "passed"
    assert any(item["rule"] == "internal.path" for item in result["findings"])


def test_current_skills_have_no_prompt_errors() -> None:
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        frontmatter, body = prompt_audit.parse_skill(path)
        result = prompt_audit.audit_text(path.parent.name, frontmatter, body)
        assert result["errors"] == 0, (path, result["findings"])
