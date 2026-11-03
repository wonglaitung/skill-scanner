from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from script_adapter import ScriptAdapter
from skill_adapter import ROOT, SkillRunResult

DEFAULT_SCRIPT = ROOT / "skills" / "md-to-word" / "scripts" / "md_to_word.py"


class MdToWordAdapter:
    def __init__(
        self,
        script_path: Path = DEFAULT_SCRIPT,
        timeout: float = 60.0,
        max_input_chars: int = 1_000_000,
    ) -> None:
        self.script_path = Path(script_path)
        self.timeout = timeout
        self.max_input_chars = max_input_chars

    @classmethod
    def from_env(cls) -> MdToWordAdapter:
        return cls(
            script_path=Path(
                os.environ.get("MD_TO_WORD_SCRIPT", DEFAULT_SCRIPT)
            ),
            timeout=float(os.environ.get("MD_TO_WORD_TIMEOUT", "60")),
            max_input_chars=int(
                os.environ.get("MD_TO_WORD_MAX_INPUT_CHARS", "1000000")
            ),
        )

    def convert(self, markdown_text: str) -> SkillRunResult:
        if len(markdown_text) > self.max_input_chars:
            raise ValueError(
                f"markdown input too large: {len(markdown_text)} > {self.max_input_chars}"
            )
        if not self.script_path.exists():
            return SkillRunResult(
                output="",
                metadata={"error": f"script not found: {self.script_path}"},
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.md"
            output_path = tmp_path / "output.docx"
            input_path.write_text(markdown_text, encoding="utf-8")

            adapter = ScriptAdapter(
                command=[
                    sys.executable,
                    str(self.script_path),
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                timeout=self.timeout,
            )
            result = adapter.run()

            if result.exit_code != 0 or not output_path.exists():
                return SkillRunResult(
                    output="",
                    metadata={
                        "error": "conversion failed",
                        "exit_code": result.exit_code,
                        "stderr": result.stderr[-2000:],
                        "latency_ms": result.latency_ms,
                    },
                )

            try:
                from docx import Document
            except ImportError:
                return SkillRunResult(
                    output="",
                    metadata={"error": "python-docx is not installed"},
                )

            document = Document(str(output_path))
            parts = [p.text for p in document.paragraphs if p.text]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))

            return SkillRunResult(
                output="\n".join(parts),
                metadata={
                    "exit_code": result.exit_code,
                    "stderr": result.stderr[-2000:],
                    "latency_ms": result.latency_ms,
                    "docx_size": output_path.stat().st_size,
                },
            )
