#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv-harness"

if [ ! -f "$VENV/bin/activate" ]; then
  echo "harness venv not found: $VENV" >&2
  echo "run: ./scripts/setup_harness_env.sh" >&2
  exit 2
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
exec "$@"
