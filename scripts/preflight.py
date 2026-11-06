#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
DEEPEVAL_SKILLS = {"write-report", "system-specification", "manager-report"}
MIN_PROMPT_LEVEL = {"S0": 1, "S1": 1, "S2": 2, "S3": 3}
LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not terminated")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def infer_kind(skill: str, metadata: dict) -> str:
    if metadata.get("tool-set") or metadata.get("tool-permissions"):
        return "tool"
    if (SKILLS_DIR / skill / "scripts").exists():
        return "script"
    return "prompt"


def minimum_level(risk: str, kind: str) -> int:
    if kind == "script":
        return 1
    if kind == "tool":
        return 2
    return MIN_PROMPT_LEVEL[risk]


def run_json(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(
        cmd, cwd=ROOT, text=True, capture_output=True, timeout=120
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {}
    return proc.returncode, data


def target_preflight(args: argparse.Namespace) -> int:
    checks: list[dict] = []

    def add(status: str, name: str, message: str) -> None:
        checks.append({"status": status, "name": name, "message": message})

    root = args.targets.expanduser().resolve()
    target_dir = root / args.skill
    if not target_dir.exists():
        add("FAIL", "target", f"not found: {target_dir}")
        return finish(checks, args.json)

    manifest_path = target_dir / "manifest.yaml"
    if not manifest_path.exists():
        add("FAIL", "manifest", f"not found: {manifest_path}")
        return finish(checks, args.json)
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        add("FAIL", "manifest", str(exc))
        return finish(checks, args.json)

    required = ["name", "owner", "risk", "type", "level", "agent", "skill"]
    missing = [key for key in required if key not in manifest]
    if missing:
        add("FAIL", "manifest", f"missing fields: {', '.join(missing)}")
        return finish(checks, args.json)
    if manifest["name"] != args.skill:
        add("FAIL", "manifest", "name does not match skill argument")
    if manifest["risk"] not in MIN_PROMPT_LEVEL:
        add("FAIL", "risk", "manifest.risk must be S0-S3")
    if manifest["type"] not in {"prompt", "tool", "script"}:
        add("FAIL", "type", "manifest.type must be prompt/tool/script")
    if manifest["level"] not in LEVELS:
        add("FAIL", "level", "manifest.level must be L0-L3")
    min_level = minimum_level(str(manifest["risk"]), str(manifest["type"]))
    selected = LEVELS[str(manifest["level"])]
    if selected < min_level:
        add("FAIL", "minimum", f"needs L{min_level}, manifest has {manifest['level']}")
    else:
        add("OK", "minimum", f"{manifest['risk']} {manifest['type']} L{min_level}+")

    if str(manifest["type"]) == "tool" and not manifest["agent"]:
        add("FAIL", "agent", "tool target must set agent: true")
    if str(manifest["type"]) != "tool" and manifest["agent"]:
        add("WARN", "agent", "non-tool target does not need agent")

    for key in ["skill", "promptfoo", "deepeval", "baseline"]:
        value = manifest.get(key)
        if value is None:
            if key == "promptfoo" and selected < 1:
                continue
            if key == "deepeval" and (selected < 2 or manifest["type"] == "script"):
                continue
            add("FAIL", key, "missing manifest path")
            continue
        path = (target_dir / str(value)).resolve()
        try:
            path.relative_to(target_dir)
        except ValueError:
            add("FAIL", key, "path escapes target directory")
            continue
        add("OK" if path.exists() else "FAIL", key, str(path.relative_to(target_dir)))

    if str(manifest["type"]) == "tool":
        for key in ["tools", "adapter"]:
            value = manifest.get(key)
            if not value:
                add("FAIL", key, "tool target requires this field")
                continue
            path = (target_dir / str(value)).resolve()
            try:
                path.relative_to(target_dir)
            except ValueError:
                add("FAIL", key, "path escapes target directory")
                continue
            add("OK" if path.exists() else "FAIL", key, str(path.relative_to(target_dir)))

    skill_path = (target_dir / str(manifest["skill"])).resolve()
    if skill_path.exists():
        proc = subprocess.run(  # nosemgrep
            [  # nosemgrep
                sys.executable,
                "scripts/prompt_audit.py",
                "--path",
                str(skill_path),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        try:
            prompt_data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            prompt_data = {}
        if prompt_data.get("errors", 0):
            add("FAIL", "prompt-audit", f"{prompt_data['errors']} errors")
        else:
            add("OK", "prompt-audit", f"{prompt_data.get('warnings', 0)} warnings")

    if not args.skip_network:
        try:
            with urllib.request.urlopen("http://localhost:8086/v1/models", timeout=2):
                add("OK", "gateway", "http://localhost:8086/v1")
        except Exception as exc:  # noqa: BLE001
            add("FAIL", "gateway", str(exc))

    if manifest["agent"]:
        harness = ROOT / ".venv-harness" / "bin" / "python"
        add("OK" if harness.exists() else "FAIL", "harness", str(harness.relative_to(ROOT)))

    if selected >= 3:
        garak = ROOT / ".venv-garak" / "bin" / "python"
        add("OK" if garak.exists() else "FAIL", "garak", str(garak.relative_to(ROOT)))

    baseline = (target_dir / str(manifest.get("baseline") or "")).resolve()
    if baseline.exists():
        try:
            data = json.loads(baseline.read_text(encoding="utf-8"))
            runs = data.get("aggregate", {}).get("run_count", 0) or len(data.get("runs", []))
        except json.JSONDecodeError:
            runs = 0
        add("OK" if runs >= 3 else "WARN", "baseline", f"{runs} runs")
    else:
        add("WARN", "baseline", "missing baseline")

    return finish(checks, args.json)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Skill 运行前是否满足分级矩阵")
    parser.add_argument("--skill", required=True)
    parser.add_argument("--targets", type=Path, default=None, help="目标仓库或 targets 目录")
    parser.add_argument("--risk", choices=["S0", "S1", "S2", "S3"], default=None)
    parser.add_argument("--level", choices=list(LEVELS), required=True)
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.skill):
        print(f"[FAIL] invalid skill name: {args.skill}")
        return 2
    if args.targets is not None:
        return target_preflight(args)

    checks: list[dict] = []

    def add(status: str, name: str, message: str) -> None:
        checks.append({"status": status, "name": name, "message": message})

    skill_path = SKILLS_DIR / args.skill / "SKILL.md"
    if not skill_path.exists():
        add("FAIL", "skill", f"not found: {skill_path}")
        return finish(checks, args.json)
    add("OK", "skill", str(skill_path.relative_to(ROOT)))

    try:
        frontmatter = parse_frontmatter(skill_path)
    except (ValueError, yaml.YAMLError) as exc:
        add("FAIL", "frontmatter", str(exc))
        return finish(checks, args.json)

    metadata = frontmatter.get("metadata") or {}
    risk = args.risk or metadata.get("risk-level")
    if risk not in MIN_PROMPT_LEVEL:
        add("FAIL", "risk-level", "metadata.risk-level 必须为 S0-S3")
        return finish(checks, args.json)
    owner = metadata.get("owner")
    if not owner:
        add("FAIL", "owner", "metadata.owner 未填写")
    else:
        add("OK", "owner", str(owner))

    kind = infer_kind(args.skill, metadata)
    add("OK", "kind", kind)
    min_level = minimum_level(risk, kind)
    selected_level = LEVELS[args.level]
    add("OK", "minimum", f"{risk} {kind} 最低 L{min_level}，本次 {args.level}")

    if selected_level < min_level:
        add(
            "FAIL",
            "level",
            f"{risk} {kind} 至少需要 L{min_level}，本次只有 {args.level}",
        )
    else:
        add("OK", "level", f"{args.level} 满足最低要求")

    if kind == "tool" and not args.agent:
        add("FAIL", "agent", "工具型 Skill 必须加 --agent")
    elif kind != "tool" and args.agent:
        add("WARN", "agent", "非工具型 Skill 不需要 --agent")
    else:
        add("OK", "agent", "enabled" if args.agent else "not required")

    if args.release and kind == "tool" and risk == "S3" and selected_level < 3:
        add("FAIL", "release", "高风险工具型发布前需要 L3")

    # Structural and deterministic checks
    for name, cmd in [
        ("validate", [sys.executable, "ci/validate_skill.py", "--skill", args.skill]),
        ("skill-lock", [sys.executable, "scripts/skill_lock.py", "verify", "--skill", args.skill]),
    ]:
        # 参数已做 name 校验，且使用 list 形式，不经过 shell
        # nosemgrep
        proc = subprocess.run(
            cmd,  # nosemgrep
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        add("OK" if proc.returncode == 0 else "FAIL", name, proc.stdout.strip() or proc.stderr.strip())

    # 参数已做 name 校验，且使用 list 形式，不经过 shell
    # nosemgrep
    proc = subprocess.run(
        [  # nosemgrep
            sys.executable,
            "scripts/prompt_audit.py",
            "--skill",
            args.skill,
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    try:
        prompt_data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        prompt_data = {}
    if prompt_data.get("errors", 0):
        add("FAIL", "prompt-audit", f"{prompt_data['errors']} errors")
    else:
        add("OK", "prompt-audit", f"{prompt_data.get('warnings', 0)} warnings")

    if kind == "tool":
        # 参数已做 name 校验，且使用 list 形式，不经过 shell
        # nosemgrep
        proc = subprocess.run(
            [  # nosemgrep
                sys.executable,
                "scripts/capability_audit.py",
                "--skill",
                args.skill,
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=120,
        )
        try:
            cap_data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            cap_data = {}
        if proc.returncode != 0:
            add("FAIL", "capability-audit", str(cap_data.get("errors") or proc.stderr.strip()))
        else:
            add("OK", "capability-audit", str(cap_data.get("status", "passed")))

    # Config checks
    if selected_level >= 1:
        if args.agent:
            config = ROOT / "evals" / f"promptfooconfig.{args.skill}.agent.yaml"
        else:
            config = ROOT / "evals" / f"promptfooconfig.{args.skill}.yaml"
        if config.exists():
            add("OK", "promptfoo-config", str(config.relative_to(ROOT)))
        else:
            add("FAIL", "promptfoo-config", f"missing {config.relative_to(ROOT)}")

    if selected_level >= 2 and kind != "script":
        if args.agent:
            target = ROOT / "evals" / "deepeval" / f"test_agent_{args.skill.replace('-', '_')}.py"
            if target.exists():
                add("OK", "deepeval-target", str(target.relative_to(ROOT)))
            else:
                add("FAIL", "deepeval-target", f"missing {target.relative_to(ROOT)}")
        elif args.skill in DEEPEVAL_SKILLS:
            target = ROOT / "evals" / "deepeval" / "test_s2_skills.py"
            if target.exists() and args.skill in target.read_text(encoding="utf-8"):
                add("OK", "deepeval-target", str(target.relative_to(ROOT)))
            else:
                add("FAIL", "deepeval-target", "test_s2_skills.py 未包含该 Skill")
        elif args.skill == "expense-policy-qa":
            target = ROOT / "evals" / "deepeval" / "test_skill.py"
            add("OK" if target.exists() else "FAIL", "deepeval-target", str(target.relative_to(ROOT)))
        else:
            add("FAIL", "deepeval-target", "未登记 DeepEval 映射")

    # Environment checks
    if not args.skip_network:
        try:
            with urllib.request.urlopen("http://localhost:8086/v1/models", timeout=2):
                add("OK", "gateway", "http://localhost:8086/v1")
        except Exception as exc:  # noqa: BLE001
            add("FAIL", "gateway", str(exc))

    if args.agent:
        harness = ROOT / ".venv-harness" / "bin" / "python"
        add("OK" if harness.exists() else "FAIL", "harness", str(harness.relative_to(ROOT)))

    if selected_level >= 3:
        garak = ROOT / ".venv-garak" / "bin" / "python"
        add("OK" if garak.exists() else "FAIL", "garak", str(garak.relative_to(ROOT)))

    if not shutil.which("docker"):
        add("WARN", "docker", "Docker 不在 PATH，security 步骤会跳过")

    # Baseline
    baseline = ROOT / "evals" / "baselines" / f"{args.skill}.json"
    if baseline.exists():
        try:
            data = json.loads(baseline.read_text(encoding="utf-8"))
            runs = data.get("aggregate", {}).get("run_count", 0) or len(data.get("runs", []))
        except json.JSONDecodeError:
            runs = 0
        if runs >= 3:
            add("OK", "baseline", f"{runs} runs")
        elif args.release:
            add("FAIL", "baseline", f"only {runs} runs, release needs 3")
        else:
            add("WARN", "baseline", f"only {runs} runs, release needs 3")
    elif args.release:
        add("FAIL", "baseline", "missing baseline")
    else:
        add("WARN", "baseline", "missing baseline")

    return finish(checks, args.json)


def finish(checks: list[dict], as_json: bool) -> int:
    failures = [item for item in checks if item["status"] == "FAIL"]
    warnings = [item for item in checks if item["status"] == "WARN"]
    result = {
        "status": "failed" if failures else ("warning" if warnings else "passed"),
        "failures": len(failures),
        "warnings": len(warnings),
        "checks": checks,
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            print(f"[{item['status']}] {item['name']}: {item['message']}")
        print(
            f"\nstatus: {result['status']}  failures={len(failures)}  warnings={len(warnings)}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
