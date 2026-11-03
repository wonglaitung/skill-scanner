#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
BASELINES_DIR = ROOT / "evals" / "baselines"


def latest_summary(skill: str) -> Path:
    candidates = sorted((REPORTS_DIR / skill).glob("*/summary.json"))
    if not candidates:
        raise FileNotFoundError(f"no reports found for {skill}")
    return candidates[-1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(skill: str, report: Path | None) -> int:
    summary_path = report or latest_summary(skill)
    data = load_json(summary_path)
    slim = {
        "skill": data.get("skill"),
        "level": data.get("level"),
        "timestamp": data.get("timestamp"),
        "model": data.get("model"),
        "api_base": data.get("api_base"),
        "metrics": data.get("metrics", {}),
    }
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    target = BASELINES_DIR / f"{skill}.json"
    target.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"baseline saved: {target}")
    return 0


def diff(skill: str, report: Path | None, fail_on_regression: bool) -> int:
    baseline_path = BASELINES_DIR / f"{skill}.json"
    if not baseline_path.exists():
        print(f"no baseline for {skill}; run: python scripts/baseline.py save {skill}")
        return 2

    baseline = load_json(baseline_path)
    current = load_json(report or latest_summary(skill))
    old_metrics = baseline.get("metrics", {})
    new_metrics = current.get("metrics", {})

    rows = []
    regressions = []

    def compare(name: str, old: object, new: object, higher_is_better: bool = True) -> None:
        if old is None and new is None:
            return
        rows.append((name, old, new))
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if higher_is_better and new < old:
                regressions.append(name)
            if not higher_is_better and new > old:
                regressions.append(name)

    compare(
        "promptfoo.pass_rate",
        old_metrics.get("promptfoo", {}).get("pass_rate"),
        new_metrics.get("promptfoo", {}).get("pass_rate"),
    )
    compare(
        "deepeval.pass_rate",
        old_metrics.get("deepeval", {}).get("pass_rate"),
        new_metrics.get("deepeval", {}).get("pass_rate"),
    )
    compare(
        "promptfoo.failed",
        old_metrics.get("promptfoo", {}).get("failed"),
        new_metrics.get("promptfoo", {}).get("failed"),
        higher_is_better=False,
    )

    print(f"baseline: {baseline_path}")
    print(f"current:  {report or latest_summary(skill)}")
    print()
    print(f"{'metric':30} {'baseline':>12} {'current':>12}")
    for name, old, new in rows:
        print(f"{name:30} {str(old):>12} {str(new):>12}")

    if regressions:
        print("\nregressions: " + ", ".join(regressions))
        return 1 if fail_on_regression else 0

    print("\nno numeric regression detected")
    return 0


def list_baselines() -> int:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(BASELINES_DIR.glob("*.json")):
        data = load_json(path)
        print(
            f"{path.stem:24} {data.get('timestamp', '-'):20} "
            f"level={data.get('level', '-')} model={data.get('model', '-')}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="保存与对比手工检查基线")
    sub = parser.add_subparsers(dest="command", required=True)

    save_parser = sub.add_parser("save")
    save_parser.add_argument("skill")
    save_parser.add_argument("--report", type=Path, default=None)

    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("skill")
    diff_parser.add_argument("--report", type=Path, default=None)
    diff_parser.add_argument("--fail-on-regression", action="store_true")

    sub.add_parser("list")

    args = parser.parse_args()
    if args.command == "save":
        return save(args.skill, args.report)
    if args.command == "diff":
        return diff(args.skill, args.report, args.fail_on_regression)
    return list_baselines()


if __name__ == "__main__":
    sys.exit(main())
