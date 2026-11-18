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
    run(
        [
            sys.executable,
            "scripts/skill_lock.py",
            "--targets",
            str(args.targets),
            "generate",
        ],
        timeout=120,
    )
    print(f"\nnext: fill targets/{args.name}, then run:")
    print(
        f"python scripts/release_assistant.py check --targets {args.targets} --skill {args.name}"
    )
    return 0


def command_check(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.targets, args.skill)
    run(
        [
            sys.executable,
            "scripts/skill_lock.py",
            "--targets",
            str(args.targets),
            "generate",
        ],
        timeout=120,
    )
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
        "rounds": [],
        "l3_enabled": bool(args.l3),
        "warnings": detect_template_warnings(args.targets, args.skill),
    }

    run(
        [
            sys.executable,
            "scripts/skill_lock.py",
            "--targets",
            str(args.targets),
            "generate",
        ],
        timeout=120,
    )
    code = run(base_args(args.targets, args.skill, manifest), timeout=300)
    result["steps"]["preflight"] = code
    if code != 0:
        write_summary(release_dir, result)
        return 1

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
        round_dir = release_dir / f"round-{index + 1}"
        round_dir.mkdir(parents=True, exist_ok=True)
        round_cmd = [*manual_cmd, "--out", str(round_dir)]
        print(f"\n=== manual_check round {index + 1}/{args.runs} ===", flush=True)
        code = run(round_cmd, timeout=3600)
        manual_codes.append(code)
        result["rounds"].append(
            {
                "index": index + 1,
                "status": code,
                "dir": str(round_dir.relative_to(ROOT)),
                "report": str((round_dir / "report.md").relative_to(ROOT)),
                "metrics": load_round_metrics(round_dir),
            }
        )
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
            "--report-dir",
            str(release_dir),
        ],
        timeout=300,
    )
    result["steps"]["baseline_collect"] = code

    last_report = release_dir / f"round-{args.runs}" / "summary.json"
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
            "--report",
            str(last_report),
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
    return 1 if decide_failures(result) else 0


TEMPLATE_INPUT_MARKER = "请替换为真实测试输入"


def detect_template_warnings(targets: Path, skill: str) -> list[str]:
    warnings: list[str] = []
    base = targets if targets.is_absolute() else ROOT / targets
    target_dir = base / skill
    promptfoo = target_dir / "evals" / "promptfoo.yaml"
    if promptfoo.exists() and TEMPLATE_INPUT_MARKER in promptfoo.read_text(
        encoding="utf-8"
    ):
        warnings.append("Promptfoo 用例仍是模板占位，需替换为业务用例")
    adapter = target_dir / "adapter.py"
    if adapter.exists() and "TODO: implement" in adapter.read_text(encoding="utf-8"):
        warnings.append("adapter.py 仍含 TODO 占位，需实现")
    return warnings


def load_round_metrics(round_dir: Path) -> dict:
    path = round_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "level": data.get("level"),
        "model": data.get("model"),
        "steps": [
            {"name": step.get("name"), "status": step.get("status")}
            for step in data.get("steps", [])
        ],
        "metrics": data.get("metrics", {}),
    }


def decide_failures(result: dict) -> list[str]:
    failures: list[str] = []
    steps = result.get("steps", {})
    for name in ["preflight", "baseline_collect", "gate"]:
        code = steps.get(name)
        if code is not None and code != 0:
            failures.append(name)
    for index, code in enumerate(steps.get("manual_check", []), start=1):
        if code != 0:
            failures.append(f"manual_check round {index}")
    if result.get("l3_enabled"):
        code = steps.get("l3")
        if code is not None and code != 0:
            failures.append("l3")
    return failures


def write_summary(out: Path, result: dict) -> None:
    failures = decide_failures(result)
    result["failures"] = failures
    result["decision"] = "FAIL" if failures else "PASS"
    (out / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Release Assistant Summary",
        "",
        f"- Skill: {result['skill']}",
        f"- Targets: {result['targets']}",
        f"- Timestamp: {result['timestamp']}",
        f"- Decision: {result['decision']}",
        "",
        "## Steps",
        "",
    ]
    for name, value in result.get("steps", {}).items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Failure Reasons", ""])
    if failures:
        lines.extend(f"- {item}" for item in failures)
    else:
        lines.append("- 无")

    lines.extend(["", "## Warnings", ""])
    warnings = result.get("warnings", [])
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("- 无")

    rounds = result.get("rounds", [])
    lines.extend(
        [
            "",
            "## Rounds",
            "",
            "| 轮次 | 状态 | 报告 | Promptfoo | DeepEval |",
            "|---|---|---|---|---|",
        ]
    )
    for rnd in rounds:
        metrics = rnd.get("metrics", {}).get("metrics", {})
        pf = metrics.get("promptfoo") or {}
        de = metrics.get("deepeval") or {}
        lines.append(
            f"| {rnd['index']} | {rnd['status']} | {rnd['report']} | "
            f"{pf.get('pass_rate', '-')} | {de.get('pass_rate', '-')} |"
        )
    if not rounds:
        lines.append("| 无 | - | - | - | - |")

    for rnd in rounds:
        found = (rnd.get("metrics", {}).get("metrics", {}).get("promptfoo") or {})
        findings = found.get("findings", [])
        if findings:
            lines.extend(["", f"### 第 {rnd['index']} 轮失败用例", ""])
            for item in findings[:10]:
                lines.append(f"- {item.get('input', '-')} -> {item.get('reason', '-')}")

    if result.get("garak"):
        lines.extend(
            ["", "## Garak", "", f"- status: {result['garak'].get('status')}"]
        )

    lines.extend(["", "## Evidence", "", f"- summary.json：{out / 'summary.json'}"])
    for rnd in rounds:
        lines.append(f"- 第 {rnd['index']} 轮报告：{ROOT / rnd['report']}")
    if result.get("garak"):
        lines.append(f"- Garak 报告前缀：{out / 'garak'}")
    lines.append("")

    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
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
    if os.environ.get("SKILL_IN_DOCKER") != "1":
        print(
            "[FAIL] 检查必须在 Docker 容器内运行；请使用 scripts/check_in_docker.sh",
            file=sys.stderr,
        )
        return 2
    if args.command == "init":
        return command_init(args)
    if args.command == "check":
        return command_check(args)
    return command_run(args)


if __name__ == "__main__":
    sys.exit(main())
