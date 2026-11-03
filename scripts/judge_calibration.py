#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "evals" / "judge_calibration" / "relevancy.jsonl"
REPORTS_DIR = ROOT / "reports" / "judge_calibration"


def load_cases(path: Path) -> list[dict]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(json.loads(line))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="使用人工标注集校准本地 Judge")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--min-agreement", type=float, default=0.8)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    os.environ.setdefault("DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE", "300")
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

    try:
        from deepeval.metrics import AnswerRelevancyMetric
        from deepeval.models import LocalModel
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        print(f"[FAIL] deepeval not installed: {exc}")
        return 2

    cases = load_cases(args.dataset)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("[FAIL] empty dataset")
        return 2

    judge = LocalModel(
        model=os.getenv("JUDGE_MODEL", "qwen3"),
        base_url=os.getenv(
            "JUDGE_API_BASE", os.getenv("SKILL_API_BASE", "http://localhost:8086/v1")
        ),
        api_key=os.getenv(
            "JUDGE_API_KEY", os.getenv("SKILL_API_KEY", "local-placeholder")
        ),
        temperature=0,
    )
    metric = AnswerRelevancyMetric(threshold=args.threshold, model=judge)

    results = []
    for case in cases:
        result = {
            "id": case.get("id"),
            "input": case.get("input"),
            "output": case.get("output"),
            "human_pass": bool(case.get("human_pass")),
            "rationale": case.get("rationale"),
            "score": None,
            "judge_pass": None,
            "agreement": None,
            "reason": None,
            "error": None,
        }
        try:
            metric.measure(
                LLMTestCase(
                    input=case["input"],
                    actual_output=case["output"],
                )
            )
            result["score"] = metric.score
            result["judge_pass"] = bool(metric.score >= args.threshold)
            result["agreement"] = result["judge_pass"] == result["human_pass"]
            result["reason"] = metric.reason
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
            result["agreement"] = False
        results.append(result)
        print(
            f"{result['id']} human={'PASS' if result['human_pass'] else 'FAIL'} "
            f"judge={result['judge_pass']} score={result['score']} "
            f"{'agree' if result['agreement'] else 'MISMATCH'}"
        )

    total = len(results)
    agreed = sum(1 for item in results if item["agreement"])
    errors = sum(1 for item in results if item["error"])
    scored = [item for item in results if isinstance(item["score"], (int, float))]
    mae = (
        sum(
            abs(item["score"] - (1.0 if item["human_pass"] else 0.0))
            for item in scored
        )
        / len(scored)
        if scored
        else None
    )
    agreement = round(agreed / total, 4) if total else 0.0
    mismatches = [item for item in results if not item["agreement"]]

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    out = args.out or REPORTS_DIR / timestamp
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": str(args.dataset.relative_to(ROOT)),
        "threshold": args.threshold,
        "min_agreement": args.min_agreement,
        "total": total,
        "agreed": agreed,
        "agreement": agreement,
        "mae": round(mae, 4) if mae is not None else None,
        "errors": errors,
        "mismatches": mismatches,
        "results": results,
    }
    (out / "judge_calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Judge 校准",
        "",
        f"- 数据集：{payload['dataset']}",
        f"- 样本数：{total}",
        f"- 阈值：{args.threshold}",
        f"- 一致率：{agreement:.2%}（目标 ≥ {args.min_agreement:.0%}）",
        f"- 平均绝对误差：{payload['mae']}",
        f"- 错误：{errors}",
        "",
        "## 不一致样本",
        "",
        "| ID | 人工 | Judge | 分数 | 原因 |",
        "|---|---|---|---|---|",
    ]
    if mismatches:
        for item in mismatches:
            lines.append(
                f"| {item['id']} | {'PASS' if item['human_pass'] else 'FAIL'} | "
                f"{item['judge_pass']} | {item['score']} | {item['reason'] or item['error']} |"
            )
    else:
        lines.append("| 无 | - | - | - | - |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print(f"agreement={agreement:.2%} mae={payload['mae']} errors={errors}")
    print(f"report: {out / 'report.md'}")
    if agreement < args.min_agreement or errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
