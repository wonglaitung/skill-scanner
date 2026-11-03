#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SKILL="${SKILL:-write-report}"
PORT="${GARAK_PORT:-8091}"
SPEC="${GARAK_SPEC:-probes.dan.Dan_11_0}"
GENERATIONS="${GARAK_GENERATIONS:-1}"
API_BASE="${SKILL_API_BASE:-http://localhost:8086/v1}"
MODEL="${SKILL_MODEL:-qwen3}"
CONFIG="$(mktemp /tmp/garak-skill-XXXXXX.json)"

cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$CONFIG"
}
trap cleanup EXIT

python3 adapters/skill_server.py \
  --skill "$SKILL" \
  --port "$PORT" \
  --api-base "$API_BASE" \
  --model "$MODEL" >/tmp/garak-skill-server.log 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 50); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

python3 - "$PORT" >"$CONFIG" <<'PY'
import json
import sys

port = sys.argv[1]
config = {
    "rest": {
        "RestGenerator": {
            "uri": f"http://127.0.0.1:{port}/v1/chat/completions",
            "method": "post",
            "headers": {"Content-Type": "application/json"},
            "req_template_json_object": {
                "model": "qwen3",
                "messages": [{"role": "user", "content": "$INPUT"}],
                "temperature": 0,
            },
            "response_json": True,
            "response_json_field": "$.choices[0].message.content",
            "request_timeout": 180,
        }
    }
}
print(json.dumps(config))
PY

mkdir -p reports
python -m garak \
  --target_type rest \
  -G "$CONFIG" \
  --spec "$SPEC" \
  --generations "$GENERATIONS" \
  --report_prefix "$ROOT/reports/garak_${SKILL}"
