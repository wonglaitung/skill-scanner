#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quarantine import active_entries, match  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
BASELINES_DIR = ROOT / "evals" / "baselines"
SCHEMA_VERSION = 2


def latest_summary(skill: str) -> Path:
    candidates = sorted((REPORTS_DIR / skill).glob("*/summary.json"))
    if not candidates:
        raise FileNotFoundError(f"no reports found for {skill}")
    return candidates[-1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_values(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    return {
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.pstdev(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "n": len(values),
    }


def case_key(item: dict) -> str:
    user_input = (item.get("vars") or {}).get("user_input") or ""
    return f"{item.get('testIdx')}|{item.get('provider')}|{user_input}"


def promptfoo_cases(path: Path, quarantine: list[dict] | None = None) -> dict:
    if not path.exists():
        return {}
    try:
        data = load_json(path)
    except json.JSONDecodeError:
        return {}

    quarantine = quarantine or []
    cases = {}
    for item in data.get("results", {}).get("results", []):
        key = case_key(item)
        input_text = (item.get("vars") or {}).get("user_input")
        entry = match(quarantine, input_text) if item.get("success") is not True else None
        cases[key] = {
            "input": input_text,
            "provider": item.get("provider"),
            "passed": item.get("success") is True,
            "error": bool(item.get("error")),
            "reason": item.get("failureReason") or item.get("error"),
            "quarantined": entry is not None,
        }
    return cases


def find_flaky(runs: list[dict]) -> list[dict]:
    keys: set[str] = set()
    for run in runs:
        keys.update(run.get("cases", {}))
    flaky = []
    for key in sorted(keys):
        entries = [run["cases"][key] for run in runs if key in run.get("cases", {})]
        if len(entries) < 2 or any(entry.get("quarantined") for entry in entries):
            continue
        passed = sum(1 for entry in entries if entry.get("passed"))
        if 0 < passed < len(entries):
            flaky.append(
                {
                    "case": key,
                    "input": entries[0].get("input"),
                    "provider": entries[0].get("provider"),
                    "runs": len(entries),
                    "passed": passed,
                    "failed": len(entries) - passed,
                    "pass_rate": round(passed / len(entries), 4),
                    "reasons": sorted(
                        {str(entry.get("reason")) for entry in entries if entry.get("reason")}
                    ),
                }
            )
    flaky.sort(key=lambda item: (item["pass_rate"], item["case"]))
    return flaky


def matching_summaries(
    skill: str,
    runs: int,
    level: str | None,
    agent: bool | None,
    report: Path | None,
) -> tuple[list[tuple[Path, dict]], dict]:
    paths = sorted((REPORTS_DIR / skill).glob("*/summary.json"))
    if not paths:
        raise FileNotFoundError(f"no reports found for {skill}")

    summaries = [(path.parent, load_json(path)) for path in paths]
    if report is not None:
        report = report.resolve()
        if report.name == "summary.json":
            report = report.parent
        summaries = [(path, data) for path, data in summaries if path.resolve() <= report]
        if not summaries:
            raise FileNotFoundError(f"no report at or before {report}")

    latest = summaries[-1][1]
    target_level = level if level is not None else latest.get("level")
    target_agent = agent if agent is not None else latest.get("agent")
    target_total = latest.get("metrics", {}).get("promptfoo", {}).get("total")

    selected = []
    for path, data in summaries:
        if data.get("level") != target_level:
            continue
        if agent is not None and bool(data.get("agent")) != agent:
            continue
        if target_agent is not None and bool(data.get("agent")) != bool(target_agent):
            continue
        if data.get("metrics", {}).get("promptfoo", {}).get("total") != target_total:
            continue
        selected.append((path, data))
    return selected[-runs:], latest


def collect(
    skill: str,
    runs: int,
    level: str | None,
    agent: bool | None,
    report: Path | None,
) -> int:
    selected, _ = matching_summaries(skill, runs, level, agent, report)
    if not selected:
        print(f"no matching reports for {skill}", file=sys.stderr)
        return 2
    if len(selected) < runs:
        print(
            f"warning: requested {runs} runs, found {len(selected)} matching reports",
            file=sys.stderr,
        )

    quarantine = active_entries(skill)
    run_entries = []
    for path, data in selected:
        metrics = data.get("metrics", {})
        run_entries.append(
            {
                "timestamp": data.get("timestamp") or path.name,
                "report": str(path.relative_to(ROOT)),
                "promptfoo": metrics.get("promptfoo", {}),
                "deepeval": metrics.get("deepeval", {}),
                "cases": promptfoo_cases(path / "promptfoo.json", quarantine),
            }
        )

    promptfoo_pass_rates = [
        run.get("promptfoo", {}).get("pass_rate")
        for run in run_entries
        if isinstance(run.get("promptfoo", {}).get("pass_rate"), (int, float))
    ]
    deepeval_pass_rates = [
        run.get("deepeval", {}).get("pass_rate")
        for run in run_entries
        if isinstance(run.get("deepeval", {}).get("pass_rate"), (int, float))
    ]
    flaky = find_flaky(run_entries)
    latest = run_entries[-1]
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "skill": skill,
        "level": selected[-1][1].get("level"),
        "agent": selected[-1][1].get("agent"),
        "model": selected[-1][1].get("model"),
        "api_base": selected[-1][1].get("api_base"),
        "generated_at": run_entries[-1]["timestamp"],
        "runs": run_entries,
        "aggregate": {
            "run_count": len(run_entries),
            "promptfoo": {
                "pass_rate": summarize_values(promptfoo_pass_rates),
                "total": latest.get("promptfoo", {}).get("total"),
                "passed": summarize_values(
                    [float(run.get("promptfoo", {}).get("passed", 0)) for run in run_entries]
                ),
                "failed": summarize_values(
                    [float(run.get("promptfoo", {}).get("failed", 0)) for run in run_entries]
                ),
                "errors": summarize_values(
                    [float(run.get("promptfoo", {}).get("errors", 0)) for run in run_entries]
                ),
            },
            "deepeval": {
                "pass_rate": summarize_values(deepeval_pass_rates),
                "passed": summarize_values(
                    [
                        float(run.get("deepeval", {}).get("passed", 0))
                        for run in run_entries
                    ]
                ),
                "failed": summarize_values(
                    [
                        float(run.get("deepeval", {}).get("failed", 0))
                        for run in run_entries
                    ]
                ),
            },
        },
        "flaky": flaky,
    }

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    target = BASELINES_DIR / f"{skill}.json"
    target.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

    pf = baseline["aggregate"]["promptfoo"]["pass_rate"]
    de = baseline["aggregate"]["deepeval"]["pass_rate"]
    print(f"baseline saved: {target}")
    print(f"runs: {len(run_entries)}  promptfoo mean={pf['mean']} std={pf['std']}")
    print(f"deepeval mean={de['mean']} std={de['std']}  flaky={len(flaky)}")
    for item in flaky:
        print(f"  flaky {item['pass_rate']:.2f}  {item['input']} -> {item['reasons']}")
    return 0


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


def baseline_metric(baseline: dict, metric: str) -> tuple[float | None, dict | None]:
    if baseline.get("schema_version") == SCHEMA_VERSION:
        section, field = metric.split(".", 1)
        aggregate = baseline.get("aggregate", {}).get(section, {}).get(field, {})
        return aggregate.get("mean"), aggregate
    value = baseline.get("metrics", {}).get(metric.split(".", 1)[0], {}).get(
        metric.split(".", 1)[1]
    )
    return value, None


def diff(skill: str, report: Path | None, fail_on_regression: bool, tolerance: float) -> int:
    baseline_path = BASELINES_DIR / f"{skill}.json"
    if not baseline_path.exists():
        print(f"no baseline for {skill}; run: python scripts/baseline.py collect {skill}")
        return 2

    baseline = load_json(baseline_path)
    current = load_json(report or latest_summary(skill))
    old_pf, old_pf_agg = baseline_metric(baseline, "promptfoo.pass_rate")
    old_de, old_de_agg = baseline_metric(baseline, "deepeval.pass_rate")
    new_pf = current.get("metrics", {}).get("promptfoo", {}).get("pass_rate")
    new_de = current.get("metrics", {}).get("deepeval", {}).get("pass_rate")

    print(f"baseline: {baseline_path}")
    print(f"current:  {report or latest_summary(skill)}")
    print()
    print(f"{'metric':30} {'baseline':>12} {'current':>12}")
    for name, old, new, agg in [
        ("promptfoo.pass_rate", old_pf, new_pf, old_pf_agg),
        ("deepeval.pass_rate", old_de, new_de, old_de_agg),
    ]:
        old_text = f"{old:.4f}" if isinstance(old, (int, float)) else "-"
        if agg:
            old_text = f"{old_text}±{agg.get('std', 0):.3f}"
        new_text = f"{new:.4f}" if isinstance(new, (int, float)) else "-"
        print(f"{name:30} {old_text:>12} {new_text:>12}")

    regressions = []
    if isinstance(old_pf, (int, float)) and isinstance(new_pf, (int, float)):
        if new_pf < old_pf - tolerance:
            regressions.append("promptfoo.pass_rate")
    if isinstance(old_de, (int, float)) and isinstance(new_de, (int, float)):
        if new_de < old_de - tolerance:
            regressions.append("deepeval.pass_rate")

    flaky = baseline.get("flaky", [])
    if flaky:
        print(f"\nbaseline flaky cases: {len(flaky)}")
        for item in flaky[:10]:
            print(f"  {item['pass_rate']:.2f}  {item['input']} -> {item['reasons']}")

    if regressions:
        print("\nregressions: " + ", ".join(regressions))
        return 1 if fail_on_regression else 0

    print("\nno numeric regression detected")
    return 0


def gate(
    skill: str,
    report: Path | None,
    tolerance: float,
    min_runs: int,
    as_json: bool,
) -> int:
    baseline_path = BASELINES_DIR / f"{skill}.json"
    if not baseline_path.exists():
        print(f"no baseline for {skill}; run: python scripts/baseline.py collect {skill}")
        return 2
    baseline = load_json(baseline_path)
    if baseline.get("schema_version") != SCHEMA_VERSION:
        print(f"legacy baseline for {skill}; run collect --runs 3 first")
        return 2
    run_count = baseline.get("aggregate", {}).get("run_count", 0)
    if run_count < min_runs:
        print(f"baseline has {run_count} runs, need at least {min_runs}")
        return 2

    current_path = report or latest_summary(skill)
    current = load_json(current_path)
    checks = []
    for name, section, key in [
        ("promptfoo.pass_rate", "promptfoo", "promptfoo"),
        ("deepeval.pass_rate", "deepeval", "deepeval"),
    ]:
        mean = (
            baseline.get("aggregate", {})
            .get(section, {})
            .get("pass_rate", {})
            .get("mean")
        )
        value = current.get("metrics", {}).get(key, {}).get("pass_rate")
        if mean is None and value is None:
            passed = True
        else:
            passed = (
                isinstance(mean, (int, float))
                and isinstance(value, (int, float))
                and value >= mean - tolerance
            )
        checks.append(
            {
                "metric": name,
                "baseline_mean": mean,
                "current": value,
                "tolerance": tolerance,
                "passed": passed,
            }
        )

    passed = all(check["passed"] for check in checks)
    result = {
        "skill": skill,
        "passed": passed,
        "baseline_runs": run_count,
        "baseline": str(baseline_path),
        "current": str(current_path),
        "checks": checks,
        "flaky_baseline_cases": len(baseline.get("flaky", [])),
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"gate: {'PASS' if passed else 'FAIL'}  skill={skill} runs={run_count}")
        for check in checks:
            print(
                f"  {check['metric']}: baseline={check['baseline_mean']} "
                f"current={check['current']} tolerance={check['tolerance']} "
                f"{'ok' if check['passed'] else 'regressed'}"
            )
    return 0 if passed else 1


def trend(skill: str) -> int:
    baseline_path = BASELINES_DIR / f"{skill}.json"
    if not baseline_path.exists():
        print(f"no baseline for {skill}; run: python scripts/baseline.py collect {skill}")
        return 2
    baseline = load_json(baseline_path)
    if baseline.get("schema_version") != SCHEMA_VERSION:
        print(f"{skill}: legacy single-run baseline")
        return 0
    print(f"{'timestamp':22} {'promptfoo':>12} {'deepeval':>12} {'flaky':>6}")
    for run in baseline.get("runs", []):
        pf = run.get("promptfoo", {}).get("pass_rate", "-")
        de = run.get("deepeval", {}).get("pass_rate", "-")
        print(f"{run.get('timestamp', '-'):22} {str(pf):>12} {str(de):>12} {'':>6}")
    pf = baseline.get("aggregate", {}).get("promptfoo", {}).get("pass_rate", {})
    de = baseline.get("aggregate", {}).get("deepeval", {}).get("pass_rate", {})
    print(
        f"{'mean±std':22} "
        f"{str(pf.get('mean')) + '±' + str(pf.get('std')):>12} "
        f"{str(de.get('mean')) + '±' + str(de.get('std')):>12} "
        f"{len(baseline.get('flaky', [])):>6}"
    )
    return 0


def list_baselines() -> int:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(BASELINES_DIR.glob("*.json")):
        data = load_json(path)
        if data.get("schema_version") == SCHEMA_VERSION:
            pf = data.get("aggregate", {}).get("promptfoo", {}).get("pass_rate", {})
            print(
                f"{path.stem:24} runs={data.get('aggregate', {}).get('run_count', 0):<3} "
                f"pf={pf.get('mean')} flaky={len(data.get('flaky', []))}"
            )
        else:
            print(f"{path.stem:24} single-run timestamp={data.get('timestamp', '-')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="保存、采集与对比手工检查基线")
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("skill")
    collect_parser.add_argument("--runs", type=int, default=3)
    collect_parser.add_argument("--level", default=None)
    collect_parser.add_argument("--agent", action="store_true", default=None)
    collect_parser.add_argument("--report", type=Path, default=None)

    save_parser = sub.add_parser("save")
    save_parser.add_argument("skill")
    save_parser.add_argument("--report", type=Path, default=None)

    diff_parser = sub.add_parser("diff")
    diff_parser.add_argument("skill")
    diff_parser.add_argument("--report", type=Path, default=None)
    diff_parser.add_argument("--fail-on-regression", action="store_true")
    diff_parser.add_argument("--tolerance", type=float, default=0.0)

    trend_parser = sub.add_parser("trend")
    trend_parser.add_argument("skill")

    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("skill")
    gate_parser.add_argument("--report", type=Path, default=None)
    gate_parser.add_argument("--tolerance", type=float, default=0.05)
    gate_parser.add_argument("--min-runs", type=int, default=3)
    gate_parser.add_argument("--json", action="store_true")

    sub.add_parser("list")

    args = parser.parse_args()
    if args.command == "collect":
        return collect(args.skill, args.runs, args.level, args.agent, args.report)
    if args.command == "save":
        return save(args.skill, args.report)
    if args.command == "diff":
        return diff(args.skill, args.report, args.fail_on_regression, args.tolerance)
    if args.command == "trend":
        return trend(args.skill)
    if args.command == "gate":
        return gate(args.skill, args.report, args.tolerance, args.min_runs, args.json)
    return list_baselines()


if __name__ == "__main__":
    sys.exit(main())
