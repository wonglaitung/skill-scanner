from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
REFERENCE_PATTERN = re.compile(r"`((?:references|scripts)/[^`]+)`")


class SkillMetadata(BaseModel):
    owner: str | None = None
    risk_level: str = Field(default="S1", pattern=r"^S[0-3]$")
    version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")


class SkillFrontmatter(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str = Field(..., pattern=r"^[a-z0-9-]{1,64}$")
    description: str = Field(..., min_length=1, max_length=1024)
    license: str | None = None
    allowed_tools: list[str] = Field(default_factory=list, alias="allowed-tools")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata)


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not terminated")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return data


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")

    try:
        frontmatter = parse_frontmatter(text)
        parsed = SkillFrontmatter.model_validate(frontmatter)
    except (ValueError, ValidationError, yaml.YAMLError) as exc:
        return [str(exc)]

    if path.parent.name != parsed.name:
        errors.append(
            f"directory name '{path.parent.name}' does not match skill name '{parsed.name}'"
        )

    for reference in REFERENCE_PATTERN.findall(text):
        if not (path.parent / reference).exists():
            errors.append(f"referenced file not found: {reference}")

    return errors


def main() -> int:
    paths = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not paths:
        print(f"[FAIL] no skills found under {SKILLS_DIR}")
        return 1

    failed = False
    for path in paths:
        errors = validate_skill(path)
        relative = path.relative_to(ROOT)
        if errors:
            failed = True
            print(f"[FAIL] {relative}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[OK] {relative}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
