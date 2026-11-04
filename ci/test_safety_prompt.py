from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters"))

from safety_prompt import SAFETY_PROMPT  # noqa: E402
from skill_adapter import LocalGatewayAdapter  # noqa: E402


def test_safety_prompt_is_appended(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("# demo\n\nOnly answer balance questions.\n", encoding="utf-8")
    adapter = LocalGatewayAdapter(
        skill_path=skill,
        api_base="http://localhost:8086/v1",
        model="qwen3",
        api_key="test",
    )
    assert "Only answer balance questions" in adapter.system_prompt
    assert SAFETY_PROMPT in adapter.system_prompt
    assert "仇恨言论" in adapter.system_prompt
