from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "capability_audit", ROOT / "scripts" / "capability_audit.py"
)
capability_audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(capability_audit)


def declared(**overrides):
    data = {
        "name": "demo",
        "allowed_tools": ["read_balance", "get_user"],
        "tool_set": "query",
        "permissions": [
            {
                "name": "read_balance",
                "scopes": ["read:balance"],
                "side-effects": "none",
                "data-access": ["self"],
            },
            {
                "name": "get_user",
                "scopes": ["read:self"],
                "side-effects": "none",
                "data-access": ["self"],
            },
        ],
    }
    data.update(overrides)
    return data


def test_audit_passes() -> None:
    result = capability_audit.audit_skill(
        declared(),
        ["read_balance", "get_user"],
        [{"name": "read_balance"}, {"name": "get_user"}],
    )
    assert result["status"] == "passed"
    assert result["errors"] == []


def test_audit_detects_missing_implementation() -> None:
    result = capability_audit.audit_skill(declared(), ["read_balance"])
    assert result["status"] == "failed"
    assert any("get_user: declared but not implemented" in item for item in result["errors"])


def test_audit_detects_undeclared_trace_call() -> None:
    result = capability_audit.audit_skill(
        declared(), ["read_balance", "get_user"], [{"name": "delete_account"}]
    )
    assert result["status"] == "failed"
    assert any("delete_account: observed in trace" in item for item in result["errors"])


def test_audit_detects_allowed_tools_mismatch() -> None:
    result = capability_audit.audit_skill(
        declared(allowed_tools=["read_balance"]), ["read_balance", "get_user"]
    )
    assert result["status"] == "failed"
    assert any("get_user: declared in tool-permissions" in item for item in result["errors"])


def test_audit_skips_non_tool_skill() -> None:
    result = capability_audit.audit_skill(
        {"name": "prompt-only", "allowed_tools": [], "tool_set": None, "permissions": []},
        None,
    )
    assert result["status"] == "skipped"
