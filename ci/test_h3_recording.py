from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("harness")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters"))

from harness.testing import MockHarness  # noqa: E402
from harness_agent import HarnessAgentAdapter  # noqa: E402
from harness_tools import build_tools  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1 and start the local model gateway",
)


def test_record_and_replay(tmp_path: Path) -> None:
    adapter = HarnessAgentAdapter(
        skill_path=ROOT / "skills" / "account-balance-query" / "SKILL.md",
        model=os.getenv("SKILL_MODEL", "qwen3"),
        api_base=os.getenv("SKILL_API_BASE", "http://localhost:8086/v1"),
        tools=build_tools("query"),
        max_iterations=6,
        record_dir=tmp_path,
    )
    result = asyncio.run(adapter.invoke("查询用户 1001 的账户余额"))

    assert "1200" in result.output
    recording = tmp_path / "recording.json"
    assert recording.exists()

    mock = MockHarness()
    mock.load_recording(recording)
    replay = asyncio.run(mock.run("查询用户 1001 的账户余额"))
    assert "1200" in replay.content
