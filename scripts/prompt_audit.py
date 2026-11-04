#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

PATTERNS = [
    (
        "pii.phone",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "error",
        "发现手机号，测试数据请使用占位符",
    ),
    (
        "pii.id_card",
        re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
        "error",
        "发现身份证号，测试数据请使用占位符",
    ),
    (
        "pii.email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "warning",
        "发现邮箱地址，确认是否为合成数据",
    ),
    (
        "secret.private_key",
        re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
        "error",
        "发现私钥内容",
    ),
    (
        "secret.api_key",
        re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
        "error",
        "发现疑似 API Key",
    ),
    (
        "internal.path",
        re.compile(r"(?<![\w/])/data/[A-Za-z0-9_./-]+"),
        "warning",
        "发现内部路径，确认是否应出现在提示词中",
    ),
    (
        "internal.endpoint",
        re.compile(r"\blocalhost:\d{2,5}\b"),
        "warning",
        "发现本地端点，确认是否应出现在提示词中",
    ),
    (
        "internal.sentinel",
        re.compile(r"\b[A-Z][A-Z0-9_]{2,}_SENTINEL\b"),
        "warning",
        "发现测试哨兵值，生产 Skill 应移除",
    ),
    (
        "prompt.leak_phrase",
        re.compile(
            r"系统提示词|system\s*prompt|忽略以上.*指令|developer\s*mode|\bDAN\b",
            re.IGNORECASE,
        ),
        "error",
        "发现可能诱导泄露提示词的短语",
    ),
]

PERMISSION_DENY = re.compile(
    r"(不得|禁止|不要|不能)(?:调用|使用|执行)?\s*`?([a-z][a-z0-9_]*)`?"
)


def parse_skill(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter is not terminated")
    frontmatter = yaml.safe_load(parts[1]) or {}
    return frontmatter, parts[2]


def audit_text(skill: str, frontmatter: dict, body: str) -> dict:
    findings = []
    for line_number, line in enumerate(body.splitlines(), start=1):
        for rule, pattern, severity, message in PATTERNS:
            for match in pattern.finditer(line):
                findings.append(
                    {
                        "rule": rule,
                        "severity": severity,
                        "line": line_number,
                        "match": match.group(0),
                        "message": message,
                    }
                )

    allowed_tools = set(frontmatter.get("allowed-tools") or [])
    for match in PERMISSION_DENY.finditer(body):
        tool = match.group(2)
        if tool in allowed_tools:
            findings.append(
                {
                    "rule": "permission.contradiction",
                    "severity": "error",
                    "line": body[: match.start()].count("\n") + 1,
                    "match": match.group(0),
                    "message": f"allowed-tools 放行 {tool}，但提示词又禁止调用 {tool}",
                }
            )

    errors = [item for item in findings if item["severity"] == "error"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "skill": skill,
        "status": "failed" if errors else "passed",
        "errors": len(errors),
        "warnings": len(warnings),
        "findings": findings,
    }


def llm_review(skill: str, body: str) -> list[dict]:
    prompt = (
        "你是 Agent Skill 的提示词安全审查员。检查下面内容是否存在：\n"
        "1. 规则前后矛盾；\n"
        "2. 诱导输出系统提示词或内部规则；\n"
        "3. 内部路径、端点、密钥、测试哨兵值暴露；\n"
        "4. 真实 PII。\n"
        "只输出 JSON 数组，每项包含 rule、severity（error/warning）、message、excerpt。\n"
        "没有问题时输出 []。不要输出解释。\n\n"
        f"Skill: {skill}\n---\n{body}"
    )
    response = httpx.post(
        f"{os.getenv('SKILL_API_BASE', 'http://localhost:8086/v1').rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('SKILL_API_KEY', 'local-placeholder')}"
        },
        json={
            "model": os.getenv("SKILL_MODEL", "qwen3"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 800,
        },
        timeout=180,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("LLM review did not return a JSON array")
    findings = []
    for item in data:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity", "warning")
        if severity not in {"error", "warning"}:
            severity = "warning"
        findings.append(
            {
                "rule": f"llm.{item.get('rule', 'finding')}",
                "severity": severity,
                "line": 0,
                "match": item.get("excerpt", ""),
                "message": item.get("message", ""),
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Skill 提示词的矛盾、泄露与敏感信息")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--skill")
    group.add_argument("--path", type=Path, help="直接指定 SKILL.md 路径，用于种子集")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--llm", action="store_true", help="增加本地 qwen3 辅助审查")
    args = parser.parse_args()

    if args.path is not None:
        skill_path = args.path
        skill_name = skill_path.parent.name
    else:
        skill_path = SKILLS_DIR / args.skill / "SKILL.md"
        skill_name = args.skill
    if not skill_path.exists():
        print(f"[FAIL] skill not found: {skill_path}")
        return 2
    try:
        frontmatter, body = parse_skill(skill_path)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"[FAIL] {exc}")
        return 2

    result = audit_text(skill_name, frontmatter, body)
    if args.llm:
        try:
            result["findings"].extend(llm_review(skill_name, body))
        except Exception as exc:  # noqa: BLE001
            result["findings"].append(
                {
                    "rule": "llm.review_error",
                    "severity": "warning",
                    "line": 0,
                    "match": "",
                    "message": f"LLM 审查失败：{exc}",
                }
            )
        result["errors"] = sum(
            1 for item in result["findings"] if item["severity"] == "error"
        )
        result["warnings"] = sum(
            1 for item in result["findings"] if item["severity"] == "warning"
        )
        result["status"] = "failed" if result["errors"] else "passed"
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"skill: {result['skill']}  status: {result['status']}  "
            f"errors: {result['errors']}  warnings: {result['warnings']}"
        )
        for item in result["findings"]:
            print(
                f"  [{item['severity'].upper()}] line {item['line']} "
                f"{item['rule']}: {item['message']} ({item['match']})"
            )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
