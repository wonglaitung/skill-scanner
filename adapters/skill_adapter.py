from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from input_guard import REFUSAL, is_encoding_request
from safety_prompt import SAFETY_PROMPT

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_PATH = ROOT / "skills" / "expense-policy-qa" / "SKILL.md"


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None
    latency_ms: float | None = None


@dataclass
class SkillRunResult:
    output: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalGatewayAdapter:
    def __init__(
        self,
        skill_path: Path,
        api_base: str,
        model: str,
        api_key: str,
        timeout: float = 60.0,
        max_tokens: int | None = None,
    ) -> None:
        self.skill_path = Path(skill_path)
        if not self.skill_path.is_absolute():
            self.skill_path = (ROOT / self.skill_path).resolve()
        self.system_prompt = self.skill_path.read_text(encoding="utf-8") + SAFETY_PROMPT
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = max_tokens

    @classmethod
    def from_env(
        cls,
        skill_path: str | Path | None = None,
        model: str | None = None,
        api_base: str | None = None,
    ) -> LocalGatewayAdapter:
        return cls(
            skill_path=Path(
                skill_path or os.environ.get("SKILL_PATH", DEFAULT_SKILL_PATH)
            ),
            api_base=api_base or os.environ.get("SKILL_API_BASE", "http://localhost:8086/v1"),
            model=model or os.environ.get("SKILL_MODEL", "local-skill-model"),
            api_key=os.environ.get("SKILL_API_KEY", "local-placeholder"),
            timeout=float(os.environ.get("SKILL_TIMEOUT", "60")),
            max_tokens=int(os.environ["SKILL_MAX_TOKENS"])
            if os.environ.get("SKILL_MAX_TOKENS")
            else None,
        )

    def invoke(
        self, user_input: str, context: dict[str, Any] | None = None
    ) -> SkillRunResult:
        if is_encoding_request(user_input):
            return SkillRunResult(
                output=REFUSAL,
                metadata={"blocked": True, "guard": "encoding"},
            )
        started_at = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = httpx.post(
            f"{self.api_base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        return SkillRunResult(
            output=data["choices"][0]["message"]["content"],
            trace_id=data.get("id"),
            metadata={
                "model": self.model,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "skill": str(self.skill_path.relative_to(ROOT)),
            },
        )
