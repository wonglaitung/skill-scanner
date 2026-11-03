#!/usr/bin/env python3
"""Expose a Skill as an OpenAI-compatible chat endpoint for Garak."""
from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_adapter import LocalGatewayAdapter


def user_text(payload: dict) -> str:
    messages = payload.get("messages", [])
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
    return ""


def make_handler(adapter: LocalGatewayAdapter):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/health", "/v1/health"}:
                self._send(200, {"status": "ok"})
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/v1/chat/completions", "/chat/completions"}:
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                result = adapter.invoke(user_text(payload))
                self._send(
                    200,
                    {
                        "id": result.trace_id or f"skill-{int(time.time() * 1000)}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": adapter.model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": result.output,
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                                  "total_tokens": 0},
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"error": str(exc)})

        def _send(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()

    adapter = LocalGatewayAdapter.from_env(
        skill_path=f"skills/{args.skill}/SKILL.md",
        model=args.model,
        api_base=args.api_base,
    )
    if args.api_key:
        adapter.api_key = args.api_key
    adapter.timeout = args.timeout

    server = ThreadingHTTPServer((args.host, args.port), make_handler(adapter))
    print(
        f"Skill endpoint: http://{args.host}:{args.port}/v1/chat/completions "
        f"(skill={args.skill}, model={adapter.model}, api_base={adapter.api_base})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
