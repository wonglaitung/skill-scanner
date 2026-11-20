#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from manual_check import deepeval_reason, suggest_for_finding  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


VISIBLE_ENV = (
    "SKILL_IN_DOCKER",
    "PYTHONUNBUFFERED",
    "SKILL_API_BASE",
    "SKILL_API_KEY",
    "SKILL_MODEL",
    "JUDGE_API_BASE",
    "JUDGE_MODEL",
    "TARGETS",
    "SKILL",
    "GARAK_REPORT_PREFIX",
    "SKILL_MAX_TOKENS",
    "DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE",
)
SENSITIVE_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")


def format_env(env: dict[str, str]) -> str:
    merged = {key: os.environ[key] for key in VISIBLE_ENV if key in os.environ}
    merged.update(env)
    parts: list[str] = []
    for key in sorted(merged):
        value = merged[key]
        if any(marker in key.upper() for marker in SENSITIVE_ENV_MARKERS):
            parts.append(f"{key}=<set>" if value else f"{key}=<unset>")
        else:
            parts.append(f"{key}={value}")
    return " ".join(parts)


def run(
    cmd: list[str],
    env: dict[str, str] | None = None,
    timeout: int = 3600,
    step: tuple[int, int, str] | None = None,
    log_path: Path | None = None,
) -> int:
    if step is not None:
        current, total, label = step
        print(
            f"\n=== [{current}/{total}] {label} | 开始 {datetime.now():%H:%M:%S} ===",
            flush=True,
        )
    print("+ " + " ".join(cmd), flush=True)
    print(f"  输入 | cwd={ROOT}", flush=True)
    print(f"  输入 | env: {format_env(env or {})}", flush=True)
    if log_path is not None:
        print(f"  输入 | log: {log_path}", flush=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    log_file = None
    if log_path is not None:
        log_file = log_path.open("w", encoding="utf-8")
    code: int | None = None
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(  # nosemgrep
            cmd,
            cwd=ROOT,
            env={**os.environ, **(env or {})},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        stdout = proc.stdout
        assert stdout is not None

        def pump() -> None:
            for line in stdout:
                print(line, end="", flush=True)
                if log_file is not None:
                    log_file.write(line)
                    log_file.flush()

        pump_thread = threading.Thread(target=pump, daemon=True)
        pump_thread.start()
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pump_thread.join(timeout=5)
            raise
        pump_thread.join()
    finally:
        if log_file is not None:
            log_file.close()
        if step is not None:
            elapsed = time.monotonic() - started
            status = "OK" if code == 0 else ("FAIL" if code is not None else "ERROR")
            print(
                f"=== [{current}/{total}] {label} | {status} | {elapsed:.1f}s ===",
                flush=True,
            )
            if log_path is not None:
                print(f"  输出 | log: {log_path} | exit={code}", flush=True)
    return code if code is not None else 1


def run_tracked(
    cmd: list[str],
    step: tuple[int, int, str],
    log_path: Path,
    result: dict,
    env: dict[str, str] | None = None,
    timeout: int = 3600,
) -> int:
    code = run(cmd, env=env, timeout=timeout, step=step, log_path=log_path)
    result["logs"].append({"step": step[2], "path": str(log_path), "exit": code})
    return code


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
    code = run(cmd, timeout=120, step=(1, 2, "初始化目标包结构"))
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
        step=(2, 2, "生成完整性锁"),
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
        step=(1, 3, "生成完整性锁"),
    )
    code = run(
        base_args(args.targets, args.skill, manifest),
        timeout=300,
        step=(2, 3, "前置校验 preflight"),
    )
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
    return run(
        cmd,
        timeout=int(os.environ.get("SKILL_MANUAL_TIMEOUT", "7200")),
        step=(3, 3, "手工检查 manual_check"),
    )


def command_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.targets, args.skill)
    total_steps = 4 + args.runs + (1 if args.l3 else 0)
    started_all = time.monotonic()
    print(
        f"\n######## 发布检查 {args.skill} [{manifest.get('level', 'L1')}] "
        f"共 {total_steps} 步 | 开始 {datetime.now():%H:%M:%S} ########",
        flush=True,
    )
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    release_dir = ROOT / "reports" / args.skill / f"release-{timestamp}"
    release_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = release_dir / "logs"
    result: dict = {
        "skill": args.skill,
        "targets": str(args.targets),
        "timestamp": timestamp,
        "manifest": manifest,
        "steps": {},
        "rounds": [],
        "logs": [],
        "l3_enabled": bool(args.l3),
        "warnings": detect_template_warnings(args.targets, args.skill),
    }

    run_tracked(
        [
            sys.executable,
            "scripts/skill_lock.py",
            "--targets",
            str(args.targets),
            "generate",
        ],
        timeout=120,
        step=(1, total_steps, "生成完整性锁"),
        log_path=logs_dir / "01-skill-lock.log",
        result=result,
    )
    code = run_tracked(
        base_args(args.targets, args.skill, manifest),
        timeout=300,
        step=(2, total_steps, "前置校验 preflight"),
        log_path=logs_dir / "02-preflight.log",
        result=result,
    )
    result["steps"]["preflight"] = code
    if code != 0:
        write_summary(release_dir, result)
        print(
            f"######## 发布检查结束 | 耗时 {time.monotonic() - started_all:.1f}s | "
            f"{result['decision']} ########",
            flush=True,
        )
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
        code = run_tracked(
            round_cmd,
            timeout=int(os.environ.get("SKILL_MANUAL_TIMEOUT", "7200")),
            step=(
                2 + index + 1,
                total_steps,
                f"手工检查 第 {index + 1}/{args.runs} 轮",
            ),
            log_path=logs_dir / f"round-{index + 1}.log",
            result=result,
        )
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

    code = run_tracked(
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
        step=(3 + args.runs, total_steps, "采集基线"),
        log_path=logs_dir / "baseline-collect.log",
        result=result,
    )
    result["steps"]["baseline_collect"] = code

    last_report = release_dir / f"round-{args.runs}" / "summary.json"
    code = run_tracked(
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
        step=(4 + args.runs, total_steps, "Delta Gate 判定"),
        log_path=logs_dir / "gate.log",
        result=result,
    )
    result["steps"]["gate"] = code

    if args.l3:
        env = {
            "TARGETS": str(args.targets),
            "SKILL": args.skill,
            "GARAK_REPORT_PREFIX": str(release_dir / "garak"),
        }
        try:
            code = run_tracked(
                ["bash", "evals/garak/scan_release.sh"],
                env=env,
                timeout=int(os.environ.get("SKILL_GARAK_TIMEOUT", "7200")),
                step=(5 + args.runs, total_steps, "Garak L3 发布前扫描"),
                log_path=logs_dir / "garak-l3.log",
                result=result,
            )
        except subprocess.TimeoutExpired:
            code = 1
            result.setdefault("l3_incomplete", "Garak 扫描超时；各轮 garak.report.jsonl 可作证据")
        result["steps"]["l3"] = code
        summary = release_dir / "garak_summary.json"
        if summary.exists():
            result["garak"] = json.loads(summary.read_text(encoding="utf-8"))

    write_summary(release_dir, result)
    print(
        f"######## 发布检查结束 | 耗时 {time.monotonic() - started_all:.1f}s | "
        f"{result['decision']} ########",
        flush=True,
    )
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
    rounds = result.get("rounds", [])
    lines = [
        "# Release Assistant Summary",
        "",
        f"- Skill: {result['skill']}",
        f"- Targets: {result['targets']}",
        f"- Timestamp: {result['timestamp']}",
        f"- Decision: {result['decision']}",
        "",
        "## 关键问题",
        "",
    ]
    all_findings: list[tuple[str, str]] = []
    for rnd in rounds:
        pf = (rnd.get("metrics", {}).get("metrics", {}).get("promptfoo") or {})
        for item in pf.get("findings", []):
            all_findings.append(("Promptfoo", f"{item.get('input', '-')} -> {item.get('reason', '-')}"))
        de = (rnd.get("metrics", {}).get("metrics", {}).get("deepeval") or {})
        for name in de.get("failed_cases", []):
            all_findings.append(("DeepEval", f"{name} —— {deepeval_reason(name, de)}"))
    seen: set[str] = set()
    for source, text in all_findings:
        key = f"{source}:{text}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- [{source}] {text}")
    if not all_findings and not failures:
        lines.append("- 无")
    if not all_findings and failures:
        lines.extend(f"- [流程] {item}" for item in failures)

    lines.extend(["", "## Steps", ""])
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
                excerpt = item.get("output_excerpt") or ""
                suffix = f"；输出摘要：{excerpt}" if excerpt else ""
                sev, advice = suggest_for_finding(item.get("input"), item.get("reason"))
                lines.append(
                    f"- {item.get('input', '-')} -> {item.get('reason', '-')}{suffix}"
                )
                lines.append(f"  - 建议级别：{sev}；修改建议：{advice}")

    if result.get("garak"):
        lines.extend(
            ["", "## Garak", "", f"- status: {result['garak'].get('status')}"]
        )
    if result.get("l3_incomplete"):
        lines.extend(["", f"- 注意：{result['l3_incomplete']}"])

    lines.extend(["", "## Logs", ""])
    logs = result.get("logs", [])
    if logs:
        for item in logs:
            lines.append(f"- [{item['step']}] {item['path']} (exit={item['exit']})")
    else:
        lines.append("- 无")

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
