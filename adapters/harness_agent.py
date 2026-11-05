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
from harness.gate import DeterministicGate
from harness.testing import RecordingConfig, RecordingHarness
from harness.tools.base import Tool

from harness_tools import build_tools
from input_guard import REFUSAL, is_blocked_request
from safety_prompt import SAFETY_PROMPT
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
        record_dir: Path | None = None,
    ) -> None:
        self.system_prompt = Path(skill_path).read_text(encoding="utf-8") + SAFETY_PROMPT
        self.trace = TraceHook()
        self.gate = DeterministicGate()
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
        self.recorder = None
        self.record_path = None
        if record_dir is not None:
            record_path = Path(record_dir)
            record_path.mkdir(parents=True, exist_ok=True)
            self.recorder = RecordingHarness(
                self.agent,
                RecordingConfig(recording_dir=record_path, auto_save=True),
            )
            self.record_path = record_path / "recording.json"

    @classmethod
    def from_env(cls) -> HarnessAgentAdapter:
        return cls(
            skill_path=Path(os.environ.get("SKILL_PATH", DEFAULT_SKILL_PATH)),
            model=os.environ.get("SKILL_MODEL", "qwen3"),
            api_base=os.environ.get("SKILL_API_BASE", "http://localhost:8086/v1"),
            tools=build_tools(os.environ.get("SKILL_TOOL_SET", "default")),
            max_iterations=int(os.environ.get("SKILL_MAX_STEPS", "10")),
            api_key=os.environ.get("SKILL_API_KEY", "local-placeholder"),
            record_dir=Path(os.environ["HARNESS_RECORD_DIR"])
            if os.environ.get("HARNESS_RECORD_DIR")
            else None,
        )

    async def invoke(self, user_input: str) -> SkillRunResult:
        if is_blocked_request(user_input):
            return SkillRunResult(
                output=REFUSAL,
                metadata={"blocked": True, "guard": "encoding"},
            )
        try:
            if self.recorder is not None:
                result = await self.recorder.run(user_input)
            else:
                result = await self.agent.run(user_input)
        except ValueError as exc:
            if "Invalid input" in str(exc):
                return SkillRunResult(
                    output="无法处理该请求：被安全策略拦截。",
                    tool_calls=self.trace.calls,
                    metadata={"blocked": True, "error": str(exc)},
                )
            raise
        sources: list[str] = []
        for call in self.trace.calls:
            if call.result:
                sources.append(call.result)
            sources.extend(str(value) for value in call.arguments.values())
        verdict = self.gate.check(result.content, sources=sources)
        unsourced = (verdict.reconciliation_report or {}).get("unsourced_claims") or []
        # harness 0.1.0 的 redact 在“无 unsourced”时也会返回隔离占位，
        # 因此只在确实存在未溯源声明时采用 delivered_content。
        output = verdict.delivered_content if unsourced else result.content

        return SkillRunResult(
            output=output,
            tool_calls=self.trace.calls,
            metadata={
                "iterations": result.iterations,
                "input_tokens": result.token_usage.input_tokens,
                "output_tokens": result.token_usage.output_tokens,
                "agent_status": result.status.value,
                "gate_passed": verdict.passed,
                "gate_findings": [finding.as_dict() for finding in verdict.findings],
                "recording": str(self.record_path) if self.record_path else None,
            },
        )
