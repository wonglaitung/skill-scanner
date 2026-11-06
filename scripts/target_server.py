#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_adapter(target_dir: Path):
    sys.path.insert(0, str(target_dir))
    sys.path.insert(0, str(target_dir / "fixtures"))
    spec = importlib.util.spec_from_file_location(
        f"target_{target_dir.name.replace('-', '_')}_adapter",
        target_dir / "adapter.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise RuntimeError(f"{target_dir}/adapter.py missing run()")
    return module


def invoke(module, text: str) -> dict:
    result = module.run(text)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    if not isinstance(result, dict):
        return {"output": str(result), "metadata": {}}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    target_dir = args.targets.expanduser().resolve() / args.skill
    manifest = yaml.safe_load((target_dir / "manifest.yaml").read_text(encoding="utf-8"))
    module = load_adapter(target_dir)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send(200, {"status": "ok", "skill": args.skill})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/chat/completions":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                messages = body.get("messages") or []
                user_text = next(
                    (
                        item.get("content", "")
                        for item in reversed(messages)
                        if item.get("role") == "user"
                    ),
                    "",
                )
                result = invoke(module, user_text)
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": str(exc)})
                return
            self._send(
                200,
                {
                    "id": f"target-{args.skill}",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": result.get("output", ""),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "metadata": {
                        "skill": args.skill,
                        "type": manifest.get("type"),
                        "tool_calls": result.get("tool_calls", []),
                    },
                },
            )

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"target server {args.skill} on {args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
