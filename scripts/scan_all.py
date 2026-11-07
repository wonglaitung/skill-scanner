#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="批量检查目标包")
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--mode", choices=["preflight", "check"], default="preflight")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--only", action="append", default=None)
    parser.add_argument("--skip-network", action="store_true")
    args = parser.parse_args()

    root = args.targets.expanduser().resolve()
    inventory_path = args.inventory or (root / "inventory.yaml")
    if inventory_path.exists():
        inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
        names = inventory.get("targets") or []
    else:
        names = sorted(
            path.name for path in root.iterdir() if (path / "manifest.yaml").exists()
        )
    if args.only:
        names = [name for name in names if name in set(args.only)]
    if not names:
        print("[FAIL] no targets")
        return 2

    out = args.out or ROOT / "reports" / "batch" / datetime.now().strftime(
        "%Y-%m-%d-%H%M%S"
    )
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for name in names:
        if not re.fullmatch(r"[a-z0-9-]+", str(name)):
            results.append({"target": name, "status": "failed", "reason": "invalid target name"})
            continue
        target_dir = root / name
        manifest_path = target_dir / "manifest.yaml"
        if not manifest_path.exists():
            results.append({"target": name, "status": "failed", "reason": "manifest missing"})
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        common = [
            sys.executable,
            "scripts/preflight.py",
            "--targets",
            str(root),
            "--skill",
            name,
            "--level",
            str(manifest.get("level", "L1")),
            "--json",
        ]
        if manifest.get("agent"):
            common.append("--agent")
        if args.skip_network:
            common.append("--skip-network")
        proc = subprocess.run(  # nosemgrep
            common,  # nosemgrep
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = {"status": "failed", "failures": 1, "warnings": 0, "checks": []}
        status = "passed" if proc.returncode == 0 else "failed"
        detail = {
            "target": name,
            "type": manifest.get("type"),
            "risk": manifest.get("risk"),
            "level": manifest.get("level"),
            "agent": bool(manifest.get("agent")),
            "status": status,
            "failures": data.get("failures", 0),
            "warnings": data.get("warnings", 0),
        }
        if args.mode == "check" and status == "passed":
            cmd = [
                sys.executable,
                "scripts/manual_check.py",
                "--targets",
                str(root),
                "--skill",
                name,
                "--level",
                str(manifest.get("level", "L1")),
            ]
            if manifest.get("agent"):
                cmd.append("--agent")
            check = subprocess.run(  # nosemgrep
                cmd,  # nosemgrep
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=3600,
            )
            detail["check_exit"] = check.returncode
            if check.returncode != 0:
                detail["status"] = "failed"
        results.append(detail)
        print(f"[{detail['status'].upper()}] {name} {detail['risk']} {detail['level']}")

    payload = {"targets": str(root), "mode": args.mode, "results": results}
    (out / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 批量检查汇总",
        "",
        f"- 目标目录：{root}",
        f"- 模式：{args.mode}",
        "",
        "| Target | Type | Risk | Level | Agent | Status |",
        "|---|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['target']} | {item.get('type', '-')} | {item.get('risk', '-')} | "
            f"{item.get('level', '-')} | {item.get('agent', '-')} | {item['status']} |"
        )
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"summary: {out / 'summary.md'}")
    return 1 if any(item["status"] != "passed" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
