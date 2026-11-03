from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))

from md_to_word_adapter import MdToWordAdapter  # noqa: E402


def test_empty_input_is_safe() -> None:
    result = MdToWordAdapter().convert("")

    assert result.metadata["exit_code"] == 0
    assert result.output == ""


def test_oversized_input_is_rejected() -> None:
    adapter = MdToWordAdapter(max_input_chars=10)

    with pytest.raises(ValueError):
        adapter.convert("x" * 11)


def test_missing_script_returns_error(tmp_path: Path) -> None:
    adapter = MdToWordAdapter(script_path=tmp_path / "missing.py")
    result = adapter.convert("# 标题")

    assert result.metadata.get("error")


def test_table_content_is_preserved() -> None:
    result = MdToWordAdapter().convert("| A | B |\n|---|---|\n| 1 | 2 |\n")

    assert "A" in result.output
    assert "B" in result.output
    assert "1" in result.output
    assert "2" in result.output
