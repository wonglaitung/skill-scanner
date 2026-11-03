from __future__ import annotations

import os
from pathlib import Path

from harness import (
    AgentHarness,
    HarnessConfig,
    HookContext,
    HookPoint,
    HookResult,
    LifecycleHook,
)
from harness.tools.base import Tool

from harness_tools import build_tools
from skill_adapter import ROOT, SkillRunResult, ToolCallRecord

DEFAULT_SKILL_PATH = ROOT / "skills" / "account-balance-query" / "SKILL.md"


class TraceHook(LifecycleHook):
    def __init__(self) -> None:
        self.calls: list[ToolCallRecord] = []

    @property
    def hook_points(self) -> list[HookPoint]:
        return [HookPoint.AFTER_TOOL_EXECUTE]

    async def execute(self, context: HookContext) -> HookResult:
        if context.tool_name:
            result = context.tool_result
            self.calls.append(
                ToolCallRecord(
                    name=context.tool_name,
                    arguments=context.tool_args or {},
                    result=result.content if result else None,
                    error=result.error if result else None,
                )
            )
        return HookResult.continue_()


class HarnessAgentAdapter:
    def __init__(
        self,
        skill_path: Path,
        model: str,
        api_base: str,
        tools: list[Tool],
        max_iterations: int = 10,
        api_key: str = "local-placeholder",
    ) -> None:
        self.system_prompt = Path(skill_path).read_text(encoding="utf-8")
        self.trace = TraceHook()
        self.agent = AgentHarness(
            config=HarnessConfig(
                model=model,
                provider="openai",
                base_url=api_base,
                api_key=api_key,
                temperature=0,
                system_prompt=self.system_prompt,
                max_iterations=max_iterations,
                enable_network=False,
            ),
            tools=tools,
        )
        self.agent.add_hook(self.trace)

    @classmethod
    def from_env(cls) -> HarnessAgentAdapter:
        return cls(
            skill_path=Path(os.environ.get("SKILL_PATH", DEFAULT_SKILL_PATH)),
            model=os.environ.get("SKILL_MODEL", "qwen3"),
            api_base=os.environ.get("SKILL_API_BASE", "http://localhost:8086/v1"),
            tools=build_tools(os.environ.get("SKILL_TOOL_SET", "default")),
            max_iterations=int(os.environ.get("SKILL_MAX_STEPS", "10")),
            api_key=os.environ.get("SKILL_API_KEY", "local-placeholder"),
        )

    async def invoke(self, user_input: str) -> SkillRunResult:
        try:
            result = await self.agent.run(user_input)
        except ValueError as exc:
            if "Invalid input" in str(exc):
                return SkillRunResult(
                    output="无法处理该请求：被安全策略拦截。",
                    tool_calls=self.trace.calls,
                    metadata={"blocked": True, "error": str(exc)},
                )
            raise
        return SkillRunResult(
            output=result.content,
            tool_calls=self.trace.calls,
            metadata={
                "iterations": result.iterations,
                "input_tokens": result.token_usage.input_tokens,
                "output_tokens": result.token_usage.output_tokens,
                "agent_status": result.status.value,
            },
        )
