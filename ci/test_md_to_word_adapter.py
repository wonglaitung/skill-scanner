from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))

from md_to_word_adapter import MdToWordAdapter  # noqa: E402


def test_md_to_word_conversion() -> None:
    adapter = MdToWordAdapter(timeout=60)
    result = adapter.convert("# 标题\n\nHello **world**\n")

    assert result.output
    assert "标题" in result.output
    assert "Hello" in result.output
