from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScriptRunResult:
    output: str
    stderr: str = ""
    exit_code: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ScriptAdapter:
    def __init__(
        self,
        command: list[str],
        cwd: Path,
        timeout: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.cwd = Path(cwd)
        self.timeout = timeout
        self.env = {**os.environ, **(env or {})}

    def run(self, args: list[str] | None = None) -> ScriptRunResult:
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                [*self.command, *(args or [])],
                cwd=self.cwd,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            return ScriptRunResult(
                output=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
        except subprocess.TimeoutExpired as exc:
            return ScriptRunResult(
                output=exc.stdout or "",
                stderr=exc.stderr or f"timeout after {self.timeout}s",
                exit_code=124,
                latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
