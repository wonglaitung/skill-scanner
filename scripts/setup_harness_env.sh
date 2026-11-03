#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv-harness"

if command -v uv >/dev/null 2>&1; then
  uv venv "$VENV"
  uv pip install --python "$VENV/bin/python" -r requirements-harness.txt -r requirements-eval.txt -r requirements-dev.txt
else
  python3 -m venv "$VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r requirements-harness.txt -r requirements-eval.txt -r requirements-dev.txt
fi

"$VENV/bin/python" -c "import harness; print('harness:', harness.__file__)"
