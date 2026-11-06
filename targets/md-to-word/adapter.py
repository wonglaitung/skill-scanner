from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts" / "md_to_word.py"


def convert(markdown_text: str) -> dict:
    if len(markdown_text) > 1_000_000:
        return {"output": "", "error": "input too large", "metadata": {}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "input.md"
        output_path = tmp_path / "output.docx"
        input_path.write_text(markdown_text, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(input_path), "--output", str(output_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=float(os.getenv("MD_TO_WORD_TIMEOUT", "60")),
            check=False,
        )
        if proc.returncode != 0 or not output_path.exists():
            return {
                "output": "",
                "error": "conversion failed",
                "metadata": {"exit_code": proc.returncode, "stderr": proc.stderr[-2000:]},
            }
        try:
            from docx import Document
        except ImportError:
            return {"output": "", "error": "python-docx is not installed", "metadata": {}}
        document = Document(str(output_path))
        parts = [p.text for p in document.paragraphs if p.text]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return {
            "output": "\n".join(parts),
            "error": None,
            "metadata": {"docx_size": output_path.stat().st_size},
        }


def call_api(prompt: str, options: dict, context: dict) -> dict:
    del options, context
    result = convert(prompt)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return {"output": result["output"], "metadata": result.get("metadata", {})}


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[1] != "run":
        print("usage: adapter.py run --input <markdown>", file=sys.stderr)
        return 2
    result = convert(sys.argv[3])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
