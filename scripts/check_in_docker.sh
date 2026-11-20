#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${CHECK_IMAGE:-skill-checker:local}"
NAME="${CHECK_CONTAINER:-skill-check}"
DETACH="${DETACH:-0}"
API_BASE="${SKILL_API_BASE:-http://host.docker.internal:8086/v1}"
API_KEY="${SKILL_API_KEY:-local-placeholder}"
MODEL="${SKILL_MODEL:-qwen3}"
JUDGE_BASE="${JUDGE_API_BASE:-$API_BASE}"
JUDGE_MODEL="${JUDGE_MODEL:-$MODEL}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1 || [[ "${REBUILD:-0}" == "1" ]]; then
  echo "building $IMAGE ..."
  docker build -f adapters/sandbox/Dockerfile.checks -t "$IMAGE" "$ROOT"
fi

SOURCE_MOUNTS=()
TARGET_MOUNTS=()
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [[ "${args[i]}" == "--source" ]] && ((i + 1 < ${#args[@]})); then
    src="${args[i + 1]}"
    if [[ "$src" != /* ]]; then
      src="$PWD/$src"
    fi
    SOURCE_MOUNTS+=("-v" "$src:$src:ro")
  fi
  if [[ "${args[i]}" == "--targets" ]] && ((i + 1 < ${#args[@]})); then
    tgt="${args[i + 1]}"
    if [[ "$tgt" == /* ]]; then
      mkdir -p "$tgt"
      TARGET_MOUNTS+=("-v" "$tgt:$tgt")
    fi
  fi
done

if docker container inspect "$NAME" >/dev/null 2>&1; then
  docker rm -f "$NAME" >/dev/null
fi

RUN_ARGS=(
  --add-host host.docker.internal:host-gateway
  -v "$ROOT:/workspace"
  "${SOURCE_MOUNTS[@]}"
  "${TARGET_MOUNTS[@]}"
  -e SKILL_IN_DOCKER=1
  -e PYTHONUNBUFFERED=1
  -e SKILL_API_BASE="$API_BASE"
  -e SKILL_API_KEY="$API_KEY"
  -e SKILL_MODEL="$MODEL"
  -e JUDGE_API_BASE="$JUDGE_BASE"
  -e JUDGE_MODEL="$JUDGE_MODEL"
  -e SKILL_MANUAL_TIMEOUT="${SKILL_MANUAL_TIMEOUT:-7200}"
  -e SKILL_GARAK_TIMEOUT="${SKILL_GARAK_TIMEOUT:-7200}"
  --user "$(id -u):$(id -g)"
  -w /workspace
  "$IMAGE"
  python scripts/release_assistant.py "$@"
)

if [[ "$DETACH" == "1" ]]; then
  docker run -d --name "$NAME" "${RUN_ARGS[@]}"
  echo "container: $NAME"
  echo "follow logs: docker logs -f $NAME"
  echo "cleanup: docker rm -f $NAME"
else
  exec docker run --rm --name "$NAME" "${RUN_ARGS[@]}"
fi
