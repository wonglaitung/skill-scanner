from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import yaml
from harness import AgentHarness, HarnessConfig, HookContext, HookPoint, HookResult, LifecycleHook
from harness.gate import DeterministicGate

from safety import SAFETY_PROMPT

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from tools import build_tools  # noqa: E402

ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT = (ROOT / "SKILL.md").read_text(encoding="utf-8") + SAFETY_PROMPT


class TraceHook(LifecycleHook):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def hook_points(self) -> list[HookPoint]:
        return [HookPoint.AFTER_TOOL_EXECUTE]

    async def execute(self, context: HookContext) -> HookResult:
        if context.tool_name:
            result = context.tool_result
            self.calls.append(
                {
                    "name": context.tool_name,
                    "arguments": context.tool_args or {},
                    "result": result.content if result else None,
                    "error": result.error if result else None,
                }
            )
        return HookResult.continue_()


def default_tool_set() -> str:
    data = yaml.safe_load((ROOT / "tools.yaml").read_text(encoding="utf-8"))
    return str(data.get("tool_set") or "query")


def run_agent(user_input: str, tool_set: str | None = None) -> dict:
    if tool_set is None:
        tool_set = default_tool_set()
    trace = TraceHook()
    agent = AgentHarness(
        config=HarnessConfig(
            model=os.getenv("SKILL_MODEL", "qwen3"),
            provider="openai",
            base_url=os.getenv("SKILL_API_BASE", "http://localhost:8086/v1"),
            api_key=os.getenv("SKILL_API_KEY", "local-placeholder"),
            temperature=0,
            system_prompt=SYSTEM_PROMPT,
            max_iterations=int(os.getenv("SKILL_MAX_STEPS", "10")),
            enable_network=False,
        ),
        tools=build_tools(tool_set),
    )
    agent.add_hook(trace)
    try:
        result = asyncio.run(agent.run(user_input))
    except ValueError as exc:
        if "Invalid input" in str(exc):
            return {
                "output": "无法处理该请求：被安全策略拦截。",
                "tool_calls": trace.calls,
                "trace_id": None,
                "metadata": {"blocked": True, "error": str(exc)},
            }
        raise
    sources = []
    for call in trace.calls:
        if call["result"]:
            sources.append(str(call["result"]))
        sources.extend(str(value) for value in call["arguments"].values())
    verdict = DeterministicGate().check(result.content, sources=sources)
    return {
        "output": result.content,
        "tool_calls": trace.calls,
        "trace_id": None,
        "metadata": {"gate_passed": verdict.passed},
    }


def registry() -> dict:
    data = yaml.safe_load((ROOT / "tools.yaml").read_text(encoding="utf-8"))
    return {"tool_set": data.get("tool_set"), "tools": data.get("tools", [])}


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del context
    config = (options or {}).get("config", {}) or {}
    result = run_agent(prompt, config.get("toolSet"))
    return {"output": result["output"], "metadata": {"tool_calls": result["tool_calls"]}}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: adapter.py registry|run", file=sys.stderr)
        return 2
    if sys.argv[1] == "registry":
        print(json.dumps(registry(), ensure_ascii=False))
        return 0
    if sys.argv[1] == "run" and len(sys.argv) >= 4:
        result = run_agent(sys.argv[3])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print("usage: adapter.py run --input <text>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


def run(user_input: str) -> dict:
    return run_agent(user_input)
