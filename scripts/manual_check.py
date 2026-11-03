#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
REPORTS_DIR = ROOT / "reports"

LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
DEEPEVAL_SKILLS = {"write-report", "system-specification", "manager-report"}
SCRIPT_SKILLS = {"md-to-word"}


def tool(name: str) -> str | None:
    return shutil.which(name)


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    raise RuntimeError(f"health check timed out: {url}")


def run_step(
    name: str,
    cmd: list[str] | None,
    env: dict[str, str],
    timeout: int,
    required: bool = True,
) -> dict:
    if cmd is None:
        return {
            "name": name,
            "status": "skipped",
            "required": required,
            "reason": "tool or config not available",
        }

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        status = "passed" if proc.returncode == 0 else "failed"
        return {
            "name": name,
            "status": status,
            "required": required,
            "cmd": cmd,
            "returncode": proc.returncode,
            "elapsed_seconds": round(time.time() - started, 2),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError:
        return {
            "name": name,
            "status": "skipped",
            "required": required,
            "reason": "command not found",
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "timeout",
            "required": required,
            "cmd": cmd,
            "elapsed_seconds": round(time.time() - started, 2),
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }


def promptfoo_config(skill: str) -> Path | None:
    candidate = ROOT / "evals" / f"promptfooconfig.{skill}.yaml"
    if candidate.exists():
        return candidate
    if skill == "expense-policy-qa":
        return ROOT / "evals" / "promptfooconfig.yaml"
    return None


def deepeval_target(skill: str) -> tuple[Path, str | None] | None:
    if skill == "expense-policy-qa":
        return ROOT / "evals" / "deepeval" / "test_skill.py", None
    if skill in DEEPEVAL_SKILLS:
        target = ROOT / "evals" / "deepeval" / "test_s2_skills.py"
        expression = skill
        if skill == "system-specification":
            expression = "system-specification or system_spec_grounding"
        return target, expression
    return None


def parse_promptfoo(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    results = data.get("results", {}).get("results", [])
    passed = sum(1 for item in results if item.get("success") is True)
    failed = sum(1 for item in results if item.get("success") is False and not item.get("error"))
    errors = sum(1 for item in results if item.get("error"))
    findings = []
    for item in results:
        if item.get("success") is False or item.get("error"):
            findings.append(
                {
                    "input": item.get("vars", {}).get("user_input"),
                    "reason": item.get("failureReason") or item.get("error"),
                }
            )
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "findings": findings,
    }


def parse_deepeval(text: str, returncode: int) -> dict:
    match = re.search(
        r"Pass Rate:\s*([\d.]+)%\s*\|\s*Passed:\s*(\d+)\s*\|\s*Failed:\s*(\d+)",
        text,
    )
    if match:
        return {
            "pass_rate": float(match.group(1)) / 100,
            "passed": int(match.group(2)),
            "failed": int(match.group(3)),
        }

    pytest_passed = re.search(r"(\d+) passed", text)
    pytest_failed = re.search(r"(\d+) failed", text)
    if pytest_passed or pytest_failed:
        passed = int(pytest_passed.group(1)) if pytest_passed else 0
        failed = int(pytest_failed.group(1)) if pytest_failed else 0
        total = passed + failed
        return {
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "passed": passed,
            "failed": failed,
        }

    return {"pass_rate": 1.0 if returncode == 0 else 0.0, "raw_exit_code": returncode}


def parse_security(out: Path) -> dict:
    trivy_path = out / "trivy.sarif"
    sbom_path = out / "sbom.cdx.json"
    findings = 0
    severities: dict[str, int] = {}
    if trivy_path.exists():
        try:
            data = json.loads(trivy_path.read_text(encoding="utf-8"))
            for run in data.get("runs", []):
                for result in run.get("results", []):
                    findings += 1
                    level = result.get("level", "unknown")
                    severities[level] = severities.get(level, 0) + 1
        except json.JSONDecodeError:
            pass

    components = 0
    if sbom_path.exists():
        try:
            data = json.loads(sbom_path.read_text(encoding="utf-8"))
            components = len(data.get("components", []))
        except json.JSONDecodeError:
            pass

    return {
        "trivy_findings": findings,
        "trivy_severities": severities,
        "sbom_components": components,
    }


def build_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "SKILL_API_BASE": args.api_base,
            "SKILL_MODEL": args.model,
            "SKILL_API_KEY": args.api_key,
            "SKILL_TIMEOUT": str(args.skill_timeout),
            "JUDGE_MODEL": args.judge_model or args.model,
            "JUDGE_API_BASE": args.api_base,
            "JUDGE_API_KEY": args.api_key,
            "RUN_LLM_EVALS": "1",
            "DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE": str(args.deepeval_timeout),
        }
    )
    return env


def write_report(skill: str, level: str, out: Path, summary: dict, steps: list[dict]) -> None:
    lines = [
        f"# Skill 手工检查报告：{skill}",
        "",
        f"- 级别：{level}",
        f"- 时间：{summary['timestamp']}",
        f"- 模型：{summary['model']}",
        f"- 网关：{summary['api_base']}",
        "",
        "## 步骤结果",
        "",
        "| 步骤 | 状态 | 耗时(s) |",
        "|---|---|---|",
    ]
    for step in steps:
        lines.append(
            f"| {step['name']} | {step['status']} | {step.get('elapsed_seconds', '-')} |"
        )

    promptfoo = summary.get("metrics", {}).get("promptfoo")
    if promptfoo:
        lines.extend(
            [
                "",
                "## Promptfoo",
                "",
                f"- 用例：{promptfoo['total']}",
                f"- 通过：{promptfoo['passed']}",
                f"- 失败：{promptfoo['failed']}",
                f"- 错误：{promptfoo['errors']}",
                f"- 通过率：{promptfoo['pass_rate']}",
            ]
        )
        for finding in promptfoo.get("findings", []):
            lines.append(f"- 失败：{finding.get('input')} -> {finding.get('reason')}")

    deepeval = summary.get("metrics", {}).get("deepeval")
    if deepeval:
        lines.extend(
            [
                "",
                "## DeepEval",
                "",
                f"- 通过率：{deepeval.get('pass_rate')}",
                f"- 通过：{deepeval.get('passed', '-')}",
                f"- 失败：{deepeval.get('failed', '-')}",
            ]
        )

    security = summary.get("metrics", {}).get("security")
    if security:
        lines.extend(
            [
                "",
                "## 供应链",
                "",
                f"- 状态：{security.get('status')}",
                f"- Trivy findings：{security.get('trivy_findings', 0)}",
                f"- Trivy 严重级别：{security.get('trivy_severities', {})}",
                f"- SBOM components：{security.get('sbom_components', 0)}",
            ]
        )

    garak = summary.get("metrics", {}).get("garak")
    if garak:
        lines.extend(
            [
                "",
                "## Garak",
                "",
                f"- 状态：{garak.get('status')}",
                f"- 报告：{garak.get('report', '-')}",
            ]
        )

    lines.extend(
        [
            "",
            "## 证据",
            "",
            f"- summary.json：{out / 'summary.json'}",
            f"- 运行日志：{out / 'run.log'}",
        ]
    )
    if (out / "promptfoo.json").exists():
        lines.append(f"- Promptfoo：{out / 'promptfoo.json'}")
    if (out / "garak.report.jsonl").exists():
        lines.append(f"- Garak：{out / 'garak.report.jsonl'}")
    if (out / "trivy.sarif").exists():
        lines.append(f"- Trivy：{out / 'trivy.sarif'}")

    lines.extend(
        [
            "",
            "## 人工复核",
            "",
            "- [ ] 失败用例是否已定级",
            "- [ ] 是否已创建修复工单",
            "- [ ] 是否需要复测",
            "- [ ] 是否满足发布门禁",
            "",
        ]
    )
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="手工触发 Skill 检查")
    parser.add_argument("--skill", required=True, help="skills/ 下的目录名")
    parser.add_argument("--level", choices=LEVELS, default="L1")
    parser.add_argument("--model", default="qwen3")
    parser.add_argument("--api-base", default="http://localhost:8086/v1")
    parser.add_argument("--api-key", default="local-placeholder")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--skill-timeout", type=int, default=180)
    parser.add_argument("--deepeval-timeout", type=int, default=300)
    parser.add_argument("--promptfoo-timeout", type=int, default=1800)
    parser.add_argument("--out", default=None)
    parser.add_argument("--full-garak", action="store_true")
    parser.add_argument("--allow-failures", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9-]+", args.skill):
        print(f"[FAIL] invalid skill name: {args.skill}")
        return 2
    if not args.api_base.startswith(("http://", "https://")):
        print(f"[FAIL] invalid api base: {args.api_base}")
        return 2

    skill_path = SKILLS_DIR / args.skill / "SKILL.md"
    if not skill_path.exists():
        print(f"[FAIL] skill not found: {skill_path}")
        return 2

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out = Path(args.out) if args.out else REPORTS_DIR / args.skill / timestamp
    out.mkdir(parents=True, exist_ok=True)

    env = build_env(args)
    steps: list[dict] = []
    current_level = LEVELS[args.level]

    validate = run_step(
        "validate",
        [sys.executable, "ci/validate_skill.py", "--skill", args.skill],
        env,
        timeout=120,
    )
    steps.append(validate)
    steps.append(
        run_step(
            "skill-lock",
            [sys.executable, "scripts/skill_lock.py", "verify", "--skill", args.skill],
            env,
            timeout=60,
        )
    )

    signature_pub = ROOT / "evals" / "keys" / "public.pem"
    signature_sig = ROOT / "evals" / "skills.lock.sig"
    if signature_pub.exists() and signature_sig.exists():
        steps.append(
            run_step(
                "skill-signature",
                [sys.executable, "scripts/sign_skills.py", "verify",
                 "--public", str(signature_pub)],
                env,
                timeout=60,
            )
        )
    else:
        steps.append(
            {
                "name": "skill-signature",
                "status": "skipped",
                "required": False,
                "reason": "signature/key not configured",
            }
        )

    ruff_path = tool("ruff")
    steps.append(
        run_step(
            "ruff",
            [ruff_path, "check", "adapters", "ci", "evals", "skills", "scripts"]
            if ruff_path
            else None,
            env,
            timeout=300,
        )
    )

    semgrep_path = tool("semgrep")
    steps.append(
        run_step(
            "semgrep",
            [semgrep_path, "--config", "p/python", "--config", "p/owasp-top-ten",
             "adapters", "ci", "skills", "scripts", "--error"]
            if semgrep_path
            else None,
            env,
            timeout=600,
        )
    )

    security_env = {**env, "REPORT_DIR": str(out)}
    docker_path = tool("docker")
    security_step = run_step(
        "security",
        [tool("bash") or "bash", "ci/run_security.sh"] if docker_path else None,
        security_env,
        timeout=900,
    )
    steps.append(security_step)
    summary_security = parse_security(out)
    summary_security["status"] = security_step["status"]

    shellcheck_path = tool("shellcheck")
    shell_files = [str(path) for path in (SKILLS_DIR / args.skill).rglob("*.sh")]
    steps.append(
        run_step(
            "shellcheck",
            [shellcheck_path, *shell_files] if shellcheck_path and shell_files else None,
            env,
            timeout=300,
        )
    )

    summary = {
        "skill": args.skill,
        "level": args.level,
        "timestamp": timestamp,
        "model": args.model,
        "api_base": args.api_base,
        "steps": [],
        "metrics": {"security": summary_security},
    }

    if current_level >= 1:
        config = promptfoo_config(args.skill)
        if config is None:
            steps.append(
                {
                    "name": "promptfoo",
                    "status": "skipped",
                    "required": True,
                    "reason": "no promptfooconfig for this skill",
                }
            )
        else:
            npx = tool("npx")
            promptfoo_step = run_step(
                "promptfoo",
                [npx, "-y", "promptfoo@latest", "eval", "-c", str(config),
                 "-o", str(out / "promptfoo.json"), "--max-concurrency", "1"]
                if npx
                else None,
                env,
                timeout=args.promptfoo_timeout,
            )
            steps.append(promptfoo_step)
            summary["metrics"]["promptfoo"] = parse_promptfoo(out / "promptfoo.json")

    if current_level >= 2:
        target = deepeval_target(args.skill)
        if target is None:
            steps.append(
                {
                    "name": "deepeval",
                    "status": "skipped",
                    "required": False,
                    "reason": "no deepeval test for this skill",
                }
            )
        elif not module_available("deepeval"):
            steps.append(
                {
                    "name": "deepeval",
                    "status": "skipped",
                    "required": False,
                    "reason": "deepeval not installed",
                }
            )
        else:
            test_file, expression = target
            cmd = [sys.executable, "-m", "pytest", str(test_file), "-q"]
            if expression:
                cmd.extend(["-k", expression])
            deepeval_step = run_step(
                "deepeval",
                cmd,
                env,
                timeout=args.promptfoo_timeout,
            )
            steps.append(deepeval_step)
            summary["metrics"]["deepeval"] = parse_deepeval(
                deepeval_step.get("stdout", "") + deepeval_step.get("stderr", ""),
                deepeval_step.get("returncode", 1),
            )

    if current_level >= 3:
        if args.skill in SCRIPT_SKILLS:
            steps.append(
                {
                    "name": "garak",
                    "status": "skipped",
                    "required": False,
                    "reason": "deterministic script skill has no LLM endpoint",
                }
            )
        elif not module_available("garak"):
            steps.append(
                {
                    "name": "garak",
                    "status": "skipped",
                    "required": False,
                    "reason": "garak not installed",
                }
            )
        else:
            server_proc = None
            try:
                port = free_port()
                # 参数已校验，且使用 list 形式，不经过 shell
                # nosemgrep
                server_proc = subprocess.Popen(
                    [  # nosemgrep
                        sys.executable,
                        "adapters/skill_server.py",
                        "--skill",
                        args.skill,
                        "--port",
                        str(port),
                        "--api-base",
                        args.api_base,
                        "--model",
                        args.model,
                        "--api-key",
                        args.api_key,
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                wait_for_health(f"http://127.0.0.1:{port}/health")

                garak_config = {
                    "rest": {
                        "RestGenerator": {
                            "uri": f"http://127.0.0.1:{port}/v1/chat/completions",
                            "method": "post",
                            "headers": {"Content-Type": "application/json"},
                            "req_template_json_object": {
                                "model": args.model,
                                "messages": [
                                    {"role": "user", "content": "$INPUT"}
                                ],
                                "temperature": 0,
                            },
                            "response_json": True,
                            "response_json_field": "$.choices[0].message.content",
                            "request_timeout": 180,
                        }
                    }
                }
                config_path = out / "garak_rest_config.json"
                config_path.write_text(
                    json.dumps(garak_config), encoding="utf-8"
                )

                spec = "probes.dan.Dan_11_0"
                parallel = []
                if args.full_garak:
                    spec = "probes.promptinject.HijackHateHumans"
                    parallel = ["--parallel_attempts", "8"]
                garak_step = run_step(
                    "garak",
                    [
                        sys.executable,
                        "-m",
                        "garak",
                        "--target_type",
                        "rest",
                        "-G",
                        str(config_path),
                        "--spec",
                        spec,
                        "--generations",
                        "1",
                        *parallel,
                        "--report_prefix",
                        str(out / "garak"),
                    ],
                    env,
                    timeout=args.promptfoo_timeout,
                )
                steps.append(garak_step)
                summary["metrics"]["garak"] = {
                    "status": garak_step["status"],
                    "report": str(out / "garak.report.jsonl"),
                    "target": f"skill:{args.skill}",
                }
            except Exception as exc:  # noqa: BLE001
                steps.append(
                    {
                        "name": "garak",
                        "status": "error",
                        "required": True,
                        "reason": str(exc),
                    }
                )
            finally:
                if server_proc is not None:
                    server_proc.terminate()
                    try:
                        server_proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server_proc.kill()

    summary["steps"] = steps
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log_lines = []
    for step in steps:
        log_lines.append(f"===== {step['name']} ({step['status']}) =====")
        log_lines.append(step.get("stdout", ""))
        log_lines.append(step.get("stderr", ""))
    (out / "run.log").write_text("\n".join(log_lines), encoding="utf-8")

    write_report(args.skill, args.level, out, summary, steps)

    hard_failures = [
        step
        for step in steps
        if step.get("required", True)
        and step["status"] in {"failed", "error", "timeout"}
    ]
    print(f"报告：{out / 'report.md'}")
    print(f"固定摘要：{out / 'summary.json'}")
    if hard_failures:
        print("失败/超时：" + ", ".join(step["name"] for step in hard_failures))
        return 0 if args.allow_failures else 1
    print("全部必需步骤通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
