from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_skill import validate_skill

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SKILL = ROOT / "skills" / "expense-policy-qa" / "SKILL.md"


def test_example_skill_is_valid() -> None:
    assert validate_skill(EXAMPLE_SKILL) == []


def test_missing_frontmatter_is_rejected(tmp_path: Path) -> None:
    skill_path = tmp_path / "bad-skill" / "SKILL.md"
    skill_path.parent.mkdir()
    skill_path.write_text("# missing frontmatter\n", encoding="utf-8")

    assert validate_skill(skill_path)
