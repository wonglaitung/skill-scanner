#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], env: dict[str, str] | None = None, timeout: int = 3600) -> int:
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(  # nosemgrep
        cmd,
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode


def load_manifest(targets: Path, skill: str) -> dict:
    path = targets / skill / "manifest.yaml"
    if not path.exists():
        raise SystemExit(f"[FAIL] manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def base_args(targets: Path, skill: str, manifest: dict) -> list[str]:
    args = [
        sys.executable,
        "scripts/preflight.py",
        "--targets",
        str(targets),
        "--skill",
        skill,
        "--level",
        str(manifest.get("level", "L1")),
    ]
    if manifest.get("agent"):
        args.append("--agent")
    return args


def command_init(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "scripts/scaffold_target.py",
        "--source",
        str(args.source),
        "--name",
        args.name,
        "--owner",
        args.owner,
        "--risk",
        args.risk,
        "--type",
        args.type,
        "--level",
        args.level,
        "--targets",
        str(args.targets),
    ]
    if args.agent:
        cmd.append("--agent")
    if args.force:
        cmd.append("--force")
    code = run(cmd, timeout=120)
    if code != 0:
        return code
    if args.targets.resolve() == (ROOT / "targets").resolve():
        run([sys.executable, "scripts/skill_lock.py", "generate"], timeout=120)
    print(f"\nnext: fill targets/{args.name}, then run:")
    print(
        f"python scripts/release_assistant.py check --targets {args.targets} --skill {args.name}"
    )
    return 0


def command_check(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.targets, args.skill)
    if args.targets.resolve() == (ROOT / "targets").resolve():
        run([sys.executable, "scripts/skill_lock.py", "generate"], timeout=120)
    code = run(base_args(args.targets, args.skill, manifest), timeout=300)
    if code != 0:
        return code
    cmd = [
        sys.executable,
        "scripts/manual_check.py",
        "--targets",
        str(args.targets),
        "--skill",
        args.skill,
        "--level",
        str(manifest.get("level", "L1")),
    ]
    if manifest.get("agent"):
        cmd.append("--agent")
    if args.llm_audit:
        cmd.append("--llm-audit")
    if args.max_tokens:
        cmd.extend(["--max-tokens", str(args.max_tokens)])
    return run(cmd, timeout=3600)


def command_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.targets, args.skill)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    release_dir = ROOT / "reports" / args.skill / f"release-{timestamp}"
    release_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "skill": args.skill,
        "targets": str(args.targets),
        "timestamp": timestamp,
        "manifest": manifest,
        "steps": {},
    }

    if args.targets.resolve() == (ROOT / "targets").resolve():
        run([sys.executable, "scripts/skill_lock.py", "generate"], timeout=120)
    code = run(base_args(args.targets, args.skill, manifest), timeout=300)
    result["steps"]["preflight"] = code
    if code != 0:
        write_summary(release_dir, result)
        return code

    manual_cmd = [
        sys.executable,
        "scripts/manual_check.py",
        "--targets",
        str(args.targets),
        "--skill",
        args.skill,
        "--level",
        str(manifest.get("level", "L1")),
    ]
    if manifest.get("agent"):
        manual_cmd.append("--agent")
    if args.llm_audit:
        manual_cmd.append("--llm-audit")
    if args.max_tokens:
        manual_cmd.extend(["--max-tokens", str(args.max_tokens)])

    manual_codes = []
    for index in range(args.runs):
        print(f"\n=== manual_check round {index + 1}/{args.runs} ===", flush=True)
        manual_codes.append(run(manual_cmd, timeout=3600))
    result["steps"]["manual_check"] = manual_codes

    code = run(
        [
            sys.executable,
            "scripts/baseline.py",
            "--targets",
            str(args.targets),
            "collect",
            args.skill,
            "--runs",
            str(args.runs),
        ],
        timeout=300,
    )
    result["steps"]["baseline_collect"] = code
    code = run(
        [
            sys.executable,
            "scripts/baseline.py",
            "--targets",
            str(args.targets),
            "gate",
            args.skill,
            "--tolerance",
            str(args.tolerance),
        ],
        timeout=300,
    )
    result["steps"]["gate"] = code

    if args.l3:
        env = {
            "TARGETS": str(args.targets),
            "SKILL": args.skill,
            "GARAK_REPORT_PREFIX": str(release_dir / "garak"),
        }
        code = run(
            ["bash", "evals/garak/scan_release.sh"],
            env=env,
            timeout=3600,
        )
        result["steps"]["l3"] = code
        summary = release_dir / "garak_summary.json"
        if summary.exists():
            result["garak"] = json.loads(summary.read_text(encoding="utf-8"))

    write_summary(release_dir, result)
    failed = result["steps"].get("preflight", 1) != 0 or result["steps"].get("gate", 1) != 0
    if args.l3 and result["steps"].get("l3", 1) != 0:
        failed = True
    return 1 if failed else 0


def write_summary(out: Path, result: dict) -> None:
    (out / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Release Assistant Summary",
        "",
        f"- Skill: {result['skill']}",
        f"- Targets: {result['targets']}",
        f"- Timestamp: {result['timestamp']}",
        "",
        "## Steps",
        "",
    ]
    for name, value in result.get("steps", {}).items():
        lines.append(f"- {name}: {value}")
    if result.get("garak"):
        lines.extend(["", "## Garak", "", f"- status: {result['garak'].get('status')}"])
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"summary: {out / 'summary.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="单入口 Skill 发布检查助手")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--owner", default="TODO")
    init.add_argument("--risk", choices=["S0", "S1", "S2", "S3"], default="S2")
    init.add_argument("--type", choices=["prompt", "script", "tool"], default="prompt")
    init.add_argument("--level", choices=["L0", "L1", "L2", "L3"], default="L2")
    init.add_argument("--agent", action="store_true")
    init.add_argument("--targets", type=Path, default=ROOT / "targets")
    init.add_argument("--force", action="store_true")

    for name in ["check", "run"]:
        p = sub.add_parser(name)
        p.add_argument("--targets", type=Path, required=True)
        p.add_argument("--skill", required=True)
        p.add_argument("--llm-audit", action="store_true")
        p.add_argument("--max-tokens", type=int, default=None)
        if name == "run":
            p.add_argument("--runs", type=int, default=3)
            p.add_argument("--tolerance", type=float, default=0.05)
            p.add_argument("--l3", action="store_true")

    args = parser.parse_args()
    if args.command == "init":
        return command_init(args)
    if args.command == "check":
        return command_check(args)
    return command_run(args)


if __name__ == "__main__":
    sys.exit(main())
