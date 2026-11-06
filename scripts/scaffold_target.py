#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "targets"


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not terminated")
    return yaml.safe_load(parts[1]) or {}


def adapter_template(kind: str) -> str:
    if kind == "prompt":
        return (TEMPLATES / "write-report" / "adapter.py").read_text(encoding="utf-8")
    if kind == "script":
        return '''from __future__ import annotations

import json
import sys


def run(user_input: str) -> dict:
    # TODO: call the target script and return {"output": ..., "metadata": ...}
    return {"output": "", "metadata": {"todo": "implement script adapter"}}


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del options, context
    result = run(prompt)
    return {"output": result.get("output", ""), "metadata": result.get("metadata", {})}
'''
    return '''from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def registry() -> dict:
    data = yaml.safe_load((Path(__file__).parent / "tools.yaml").read_text(encoding="utf-8"))
    return {"tool_set": data.get("tool_set", "default"), "tools": data.get("tools", [])}


def run(user_input: str) -> dict:
    # TODO: implement tool execution and return tool_calls.
    return {"output": "", "tool_calls": [], "metadata": {"todo": "implement tool adapter"}}


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del options, context
    result = run(prompt)
    return {
        "output": result.get("output", ""),
        "metadata": {"tool_calls": result.get("tool_calls", [])},
    }
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="创建目标包骨架")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--name", default=None)
    parser.add_argument("--owner", default="TODO")
    parser.add_argument("--risk", choices=["S0", "S1", "S2", "S3"], default="S2")
    parser.add_argument("--type", choices=["prompt", "script", "tool"], default="prompt")
    parser.add_argument("--level", choices=["L0", "L1", "L2", "L3"], default="L2")
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--targets", type=Path, default=ROOT / "targets")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    skill_md = source / "SKILL.md" if source.is_dir() else source
    if not skill_md.exists():
        print(f"[FAIL] SKILL.md not found: {skill_md}")
        return 2
    try:
        frontmatter = parse_frontmatter(skill_md)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"[FAIL] {exc}")
        return 2
    name = args.name or frontmatter.get("name") or (source.name if source.is_dir() else source.stem)
    if not re.fullmatch(r"[a-z0-9-]+", str(name)):
        print(f"[FAIL] invalid name: {name}")
        return 2
    target_dir = args.targets.expanduser().resolve() / name
    if target_dir.exists() and not args.force:
        print(f"[FAIL] target exists: {target_dir} (use --force)")
        return 1

    files = []
    if source.is_dir():
        for item in source.rglob("*"):
            if item.is_file() and "__pycache__" not in item.parts:
                files.append(item.relative_to(source))
    else:
        files.append(Path("SKILL.md"))

    if args.dry_run:
        for item in files:
            print(f"would copy: {item}")
        print(f"would create: {target_dir}/manifest.yaml")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for item in files:
            dest = target_dir / item
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / item, dest)
    else:
        shutil.copy2(skill_md, target_dir / "SKILL.md")

    (target_dir / "manifest.yaml").write_text(
        f'''name: {name}
owner: {args.owner}
risk: {args.risk}
type: {args.type}
level: {args.level}
agent: {str(args.agent).lower()}
skill: SKILL.md
promptfoo: evals/promptfoo.yaml
deepeval: {"evals/test_target.py" if args.level in {"L2", "L3"} and args.type != "script" else "null"}
baseline: evals/baseline.json
tools: {"tools.yaml" if args.type == "tool" else "null"}
adapter: adapter.py
''',
        encoding="utf-8",
    )
    (target_dir / "adapter.py").write_text(adapter_template(args.type), encoding="utf-8")
    if args.type == "prompt":
        shutil.copy2(TEMPLATES / "write-report" / "safety.py", target_dir / "safety.py")
    if args.type == "tool":
        (target_dir / "tools.yaml").write_text(
            "tool_set: default\ntools: []\n", encoding="utf-8"
        )
    (target_dir / "evals").mkdir(exist_ok=True)
    (target_dir / "fixtures").mkdir(exist_ok=True)
    (target_dir / "fixtures" / "README.md").write_text(
        "只放合成测试数据。\n", encoding="utf-8"
    )
    (target_dir / "evals" / "promptfoo.yaml").write_text(
        '''# yaml-language-server: $schema=https://promptfoo.dev/config-schema.json
description: TODO
basePath: ..
prompts:
  - "{{user_input}}"
providers:
  - id: file://./adapter.py:call_api
    label: TODO
tests:
  - vars:
      user_input: "请替换为真实测试输入"
    assert:
      - type: not-contains
        value: "Traceback"
''',
        encoding="utf-8",
    )
    if args.level in {"L2", "L3"} and args.type != "script":
        (target_dir / "evals" / "test_target.py").write_text(
            '''from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("deepeval")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("target_adapter", ROOT / "adapter.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_EVALS") != "1",
    reason="set RUN_LLM_EVALS=1",
)


def test_output_not_empty() -> None:
    result = module.run("请替换为真实测试输入")
    assert result.get("output") is not None
''',
            encoding="utf-8",
        )
    print(f"target scaffolded: {target_dir}")
    print("next: fill adapter/evals/tools, then run preflight")
    return 0


if __name__ == "__main__":
    sys.exit(main())
