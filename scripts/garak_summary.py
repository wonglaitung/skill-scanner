#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_entries(path: Path) -> list[dict]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def summarize(entries: list[dict]) -> dict:
    evals = []
    for entry in entries:
        if entry.get("entry_type") != "eval":
            continue
        total = entry.get("total_evaluated") or 0
        fails = entry.get("fails") or 0
        evals.append(
            {
                "probe": entry.get("probe"),
                "detector": entry.get("detector"),
                "passed": entry.get("passed", 0),
                "fails": fails,
                "total": total,
                "attack_success_rate": round(fails / total, 4) if total else None,
                "confidence_lower": entry.get("confidence_lower"),
                "confidence_upper": entry.get("confidence_upper"),
            }
        )
    failed = [item for item in evals if item["fails"]]
    return {
        "status": "failed" if failed else "passed",
        "eval_count": len(evals),
        "failure_count": len(failed),
        "evals": evals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总 Garak JSONL 报告")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.report.exists():
        print(f"[FAIL] report not found: {args.report}")
        return 2
    result = summarize(load_entries(args.report))
    payload = {"report": str(args.report), **result}
    out = args.out or (args.report.parent / "garak_summary.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Garak 汇总",
        "",
        f"- 报告：{args.report}",
        f"- 状态：{payload['status']}",
        f"- 评估项：{payload['eval_count']}",
        f"- 失败项：{payload['failure_count']}",
        "",
        "| Probe | Detector | Pass | Fail | Total | ASR | 95% CI |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload["evals"]:
        ci = "-"
        if item["confidence_lower"] is not None:
            ci = f"{item['confidence_lower']:.2%}–{item['confidence_upper']:.2%}"
        asr = f"{item['attack_success_rate']:.2%}" if item["attack_success_rate"] is not None else "-"
        lines.append(
            f"| {item['probe']} | {item['detector']} | {item['passed']} | "
            f"{item['fails']} | {item['total']} | {asr} | {ci} |"
        )
    (out.parent / "garak_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"status={payload['status']} failures={payload['failure_count']}")
    for item in payload["evals"]:
        print(
            f"{item['probe']} {item['detector']} "
            f"ASR={item['attack_success_rate']} ({item['fails']}/{item['total']})"
        )
    print(f"summary: {out}")
    return 1 if payload["failure_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
