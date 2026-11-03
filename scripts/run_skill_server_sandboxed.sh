#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKILL="${1:-${SKILL:-write-report}}"
PORT="${PORT:-8090}"
IMAGE="${SKILL_SERVER_IMAGE:-skill-server-sandbox:local}"
CONTAINER="skill-server-sandbox-${SKILL}-$$"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -f adapters/sandbox/Dockerfile.model -t "$IMAGE" "$ROOT"
fi

docker run -d --rm --name "$CONTAINER" \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --memory 512m \
  --cpus 1 \
  --pids-limit 128 \
  --add-host host.docker.internal:host-gateway \
  -e SKILL_API_BASE="${SKILL_API_BASE:-http://host.docker.internal:8086/v1}" \
  -e SKILL_MODEL="${SKILL_MODEL:-qwen3}" \
  -e SKILL_API_KEY="${SKILL_API_KEY:-local-placeholder}" \
  -e SKILL_TIMEOUT="${SKILL_TIMEOUT:-180}" \
  -e PORT="$PORT" \
  -v "$ROOT:/workspace:ro" \
  -w /workspace \
  -p "127.0.0.1:${PORT}:${PORT}" \
  "$IMAGE" \
  --skill "$SKILL" \
  --host 0.0.0.0 \
  --port "$PORT"

echo "container: $CONTAINER"
docker wait "$CONTAINER"
