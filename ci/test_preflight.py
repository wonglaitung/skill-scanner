from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preflight", ROOT / "scripts" / "preflight.py")
preflight = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(preflight)


def test_minimum_levels() -> None:
    assert preflight.minimum_level("S0", "prompt") == 1
    assert preflight.minimum_level("S1", "prompt") == 1
    assert preflight.minimum_level("S2", "prompt") == 2
    assert preflight.minimum_level("S3", "prompt") == 3
    assert preflight.minimum_level("S2", "tool") == 2
    assert preflight.minimum_level("S3", "tool") == 2
    assert preflight.minimum_level("S2", "script") == 1


def test_infer_kind() -> None:
    assert preflight.infer_kind("account-balance-query", {"tool-set": "query"}) == "tool"
    assert preflight.infer_kind("md-to-word", {}) == "script"
    assert preflight.infer_kind("write-report", {}) == "prompt"
