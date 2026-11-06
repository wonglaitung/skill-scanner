#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "targets"
ALLOWED_SIDE_EFFECTS = {"none", "read", "write", "external", "destructive"}


def parse_skill(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not terminated")
    frontmatter = yaml.safe_load(parts[1]) or {}
    metadata = frontmatter.get("metadata") or {}
    return {
        "name": frontmatter.get("name"),
        "description": frontmatter.get("description") or "",
        "allowed_tools": frontmatter.get("allowed-tools") or [],
        "tool_set": metadata.get("tool-set") or metadata.get("tool_set"),
        "permissions": metadata.get("tool-permissions")
        or metadata.get("tool_permissions")
        or [],
    }


def audit_skill(
    declared: dict,
    registry_names: list[str] | None,
    actual_calls: list[dict] | None = None,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    allowed = list(declared.get("allowed_tools") or [])
    permissions = list(declared.get("permissions") or [])
    tool_set = declared.get("tool_set")
    actual_calls = actual_calls or []

    if not tool_set and not permissions:
        return {
            "skill": declared.get("name"),
            "status": "skipped",
            "reason": "no tool-set or tool-permissions declared",
            "errors": [],
            "warnings": [],
            "declared_tools": [],
            "registry_tools": [],
            "actual_tools": [],
        }

    names = []
    for index, entry in enumerate(permissions):
        if not isinstance(entry, dict):
            errors.append(f"tool-permissions[{index}] must be a mapping")
            continue
        name = entry.get("name")
        if not name:
            errors.append(f"tool-permissions[{index}] missing name")
            continue
        names.append(name)
        scopes = entry.get("scopes")
        if not isinstance(scopes, list) or not scopes:
            errors.append(f"{name}: scopes must be a non-empty list")
        side_effects = entry.get("side-effects") or entry.get("side_effects")
        if side_effects not in ALLOWED_SIDE_EFFECTS:
            errors.append(
                f"{name}: side-effects must be one of {sorted(ALLOWED_SIDE_EFFECTS)}"
            )
        data_access = entry.get("data-access") or entry.get("data_access")
        if not isinstance(data_access, list) or not data_access:
            errors.append(f"{name}: data-access must be a non-empty list")

    if len(names) != len(set(names)):
        errors.append("duplicate names in tool-permissions")

    allowed_set = set(allowed)
    permission_set = set(names)
    for name in sorted(permission_set - allowed_set):
        errors.append(f"{name}: declared in tool-permissions but missing from allowed-tools")
    for name in sorted(allowed_set - permission_set):
        errors.append(f"{name}: declared in allowed-tools but missing from tool-permissions")

    if not tool_set:
        errors.append("tool-permissions declared but metadata.tool-set is missing")

    registry_set = set(registry_names or [])
    if tool_set and registry_names is not None:
        for name in sorted(permission_set - registry_set):
            errors.append(f"{name}: declared but not implemented by tool-set '{tool_set}'")
        for name in sorted(registry_set - permission_set):
            warnings.append(
                f"{name}: implemented by tool-set '{tool_set}' but not declared"
            )

    actual_names = [
        call.get("name") for call in actual_calls if isinstance(call, dict) and call.get("name")
    ]
    for name in sorted(set(actual_names) - permission_set):
        errors.append(f"{name}: observed in trace but not declared")

    return {
        "skill": declared.get("name"),
        "status": "failed" if errors else "passed",
        "tool_set": tool_set,
        "declared_tools": sorted(permission_set),
        "registry_tools": sorted(registry_set),
        "actual_tools": sorted(set(actual_names)),
        "errors": errors,
        "warnings": warnings,
    }


def load_actual_calls(path: Path | None, provider: str | None = None) -> list[dict]:
    if path is None:
        return []
    target = path / "promptfoo.json" if path.is_dir() else path
    if not target.exists():
        raise FileNotFoundError(f"trace file not found: {target}")
    data = json.loads(target.read_text(encoding="utf-8"))
    calls = []
    for result in data.get("results", {}).get("results", []):
        provider_info = result.get("provider") or {}
        if provider and provider not in {
            provider_info.get("label"),
            provider_info.get("id"),
        }:
            continue
        calls.extend((result.get("metadata") or {}).get("tool_calls") or [])
    return calls


def target_audit(args: argparse.Namespace) -> int:
    target_dir = args.targets.expanduser().resolve() / args.skill
    manifest_path = target_dir / "manifest.yaml"
    tools_path = target_dir / "tools.yaml"
    adapter_path = target_dir / "adapter.py"
    if not manifest_path.exists() or not tools_path.exists() or not adapter_path.exists():
        print(f"[FAIL] incomplete target: {target_dir}")
        return 2
    data = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
    tools = data.get("tools") or []
    names = [item.get("name") for item in tools if isinstance(item, dict)]
    errors = []
    if len(names) != len(set(names)):
        errors.append("duplicate tools in tools.yaml")
    for item in tools:
        name = item.get("name") if isinstance(item, dict) else None
        if not name:
            errors.append("tool missing name")
            continue
        if not item.get("scopes"):
            errors.append(f"{name}: scopes empty")
        if item.get("side_effects") not in {"none", "read", "write", "external", "destructive"}:
            errors.append(f"{name}: invalid side_effects")
        if not item.get("data_access"):
            errors.append(f"{name}: data_access empty")

    proc = subprocess.run(  # nosemgrep
        [sys.executable, str(adapter_path), "registry"],  # nosemgrep
        cwd=target_dir,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        errors.append(f"adapter registry failed: {proc.stderr.strip()}")
        registry_names = []
    else:
        try:
            registry = json.loads(proc.stdout)
            registry_names = [item["name"] for item in registry.get("tools", [])]
        except (json.JSONDecodeError, KeyError):
            errors.append("adapter registry returned invalid JSON")
            registry_names = []

    for name in sorted(set(names) - set(registry_names)):
        errors.append(f"{name}: declared but not registered")
    for name in sorted(set(registry_names) - set(names)):
        errors.append(f"{name}: registered but not declared")

    result = {
        "skill": args.skill,
        "status": "failed" if errors else "passed",
        "declared_tools": names,
        "registry_tools": registry_names,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"skill: {args.skill}  status: {result['status']}")
        print(f"  declared: {names}")
        print(f"  registry: {registry_names}")
        for error in errors:
            print(f"  [ERROR] {error}")
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 Skill 的说明、权限与工具实现一致性")
    parser.add_argument("--skill", required=True)
    parser.add_argument("--targets", type=Path, default=None, help="目标包目录")
    parser.add_argument("--report", type=Path, default=None, help="Promptfoo 报告目录或 JSON")
    parser.add_argument(
        "--provider",
        default=None,
        help="只审计指定 Promptfoo provider 的 Trace，例如 harness-agent",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.targets is not None:
        return target_audit(args)

    skill_path = SKILLS_DIR / args.skill / "SKILL.md"
    if not skill_path.exists():
        print(f"[FAIL] skill not found: {skill_path}")
        return 2
    try:
        declared = parse_skill(skill_path)
        actual_calls = load_actual_calls(args.report, args.provider)
    except (ValueError, yaml.YAMLError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 2

    registry_names = None
    if declared.get("tool_set"):
        sys.path.insert(0, str(ROOT / "adapters"))
        try:
            from harness_tools import build_tools
        except ImportError as exc:
            print(f"[FAIL] cannot load tool registry: {exc}")
            return 2
        registry_names = [tool.name for tool in build_tools(declared["tool_set"])]

    result = audit_skill(declared, registry_names, actual_calls)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"skill: {result['skill']}  status: {result['status']}")
        if result["status"] == "skipped":
            print(f"  skipped: {result['reason']}")
        else:
            print(f"  tool-set: {result.get('tool_set')}")
            print(f"  declared: {result['declared_tools']}")
            print(f"  registry: {result['registry_tools']}")
            print(f"  actual:   {result['actual_tools']}")
            for error in result["errors"]:
                print(f"  [ERROR] {error}")
            for warning in result["warnings"]:
                print(f"  [WARN] {warning}")
    return 0 if result["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
