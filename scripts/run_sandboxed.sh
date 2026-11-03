#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${SANDBOX_IMAGE:-skill-sandbox:local}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -f adapters/sandbox/Dockerfile -t "$IMAGE" "$ROOT"
fi

docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --memory 512m \
  --cpus 1 \
  --pids-limit 128 \
  -e MD_TO_WORD_LOG=/tmp/md_to_word.log \
  -v "$ROOT:/workspace:ro" \
  -w /workspace \
  "$IMAGE" "$@"
